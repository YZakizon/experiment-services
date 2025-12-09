import unittest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from services.cache import get_mock_cache_client
import logging
import sys # <-- Import sys for mocking external modules

# --- Mock SQLAlchemy ORM models (These still need to be mocks) ---
# Define Mock ORM classes with class-level attributes for query mocking
class MockExperiment:
    # Class attributes required for query mocking (e.g., db.query(Experiment).filter(Experiment.id == x))
    id = None
    name = None
    description = None

    def __init__(self, id=None, name=None, description=None, variants=None):
        self.id = id
        self.name = name
        self.description = description
        self.variants = variants if variants is not None else []
        self.assignments = [] # Mock relationship

class MockVariant:
    # Class attributes required for query mocking
    experiment_id = None
    name = None
    allocation_percent = None

    def __init__(self, experiment_id, name, allocation_percent):
        self.experiment_id = experiment_id
        self.name = name
        self.allocation_percent = allocation_percent

class MockAssignment:
    # Class attributes required for query mocking
    user_id = None
    experiment_id = None
    variant_name = None

    def __init__(self, user_id, experiment_id, variant_name, id=1):
        self.id = id
        self.user_id = user_id
        self.experiment_id = experiment_id
        self.variant_name = variant_name

# --- Setup Mock Module Path for 'data.database' (ORM Models) ---
# This allows 'assignment.py' to import from 'data.database' successfully.
mock_db_module = MagicMock()
mock_db_module.Experiment = MockExperiment
mock_db_module.Variant = MockVariant
mock_db_module.Assignment = MockAssignment
sys.modules['data.database'] = mock_db_module
sys.modules['data'] = MagicMock() # Mock the parent module


# --- Mock Pydantic models and set up 'models.experiments' path ---
# Define placeholder classes (Pydantic models) used by the tests
class VariantAllocation:
    def __init__(self, name, allocation_percent):
        self.name = name
        self.allocation_percent = allocation_percent
class ExperimentCreate:
    def __init__(self, name, description, variants: list[VariantAllocation]):
        self.name = name
        self.description = description
        self.variants = variants

# Inject these mock Pydantic classes into the 'models.experiments' module path
mock_pydantic_module = MagicMock()
mock_pydantic_module.ExperimentCreate = ExperimentCreate
mock_pydantic_module.VariantAllocation = VariantAllocation
sys.modules['models.experiments'] = mock_pydantic_module
sys.modules['models'] = MagicMock() # Mock the parent module


# Import functions from the module under test (assuming they are in 'assignment.py')
from services.assignment import (
    create_new_experiment, 
    get_or_create_assignment,
    MAX_RETRIES # Import the retry constant
)

# Set up logging to capture output during tests
logging.basicConfig(level=logging.INFO)

# --- Unit Test Class ---

# Patch the ORM models directly in the 'assignment' module where they are imported.
@patch('services.assignment.Assignment', MockAssignment)
@patch('services.assignment.Variant', MockVariant)
@patch('services.assignment.Experiment', MockExperiment)
class TestAssignmentService(unittest.TestCase):

    def setUp(self):
        # Only mock the database session object, which is passed as an argument.
        self.mock_db = MagicMock()
        self.mock_cache_client = get_mock_cache_client()
        # No need for patcher/patch.dict setup/teardown anymore.

    def tearDown(self):
        # Clean up is no longer needed here as patches are handled by the decorators.
        pass

    # --- Test Cases for create_new_experiment ---

    def test_create_new_experiment_happy_path(self):
        """Tests successful creation of an experiment and its variants using Pydantic models, specifically for a purchase button test."""
        
        new_experiment_name = "Testing red vs blue for purchase button clicks."
        
        # 1. Prepare Pydantic VariantAllocation models with specific variant names
        variant_data = [
            VariantAllocation(name='red_button', allocation_percent=50),
            VariantAllocation(name='blue_button', allocation_percent=50)
        ]
        
        # 2. Prepare Pydantic ExperimentCreate model with specific experiment name
        experiment_data = ExperimentCreate(
            name=new_experiment_name,
            description="A/B test the color of the primary purchase button on the checkout page.",
            variants=variant_data
        )
        
        # Mock db.flush() to simulate setting the ID on the ORM object
        def mock_flush():
            # Simulate the database setting the ID on the Python ORM object
            db_obj = self.mock_db.add.call_args_list[0].args[0]
            db_obj.id = 100 

        self.mock_db.flush.side_effect = mock_flush
        self.mock_db.refresh.side_effect = lambda x: None # Mock refresh to do nothing complex

        # Execute the function
        result = create_new_experiment(self.mock_db, experiment_data)

        # Assertions
        # Check that the first call to add was with an Experiment instance
        self.assertTrue(isinstance(self.mock_db.add.call_args_list[0].args[0], MockExperiment)) 
        self.assertEqual(self.mock_db.add.call_count, 3) # 1 Experiment + 2 Variants
        self.mock_db.flush.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.assertEqual(result.id, 100)
        # Assert the new, specific name
        self.assertEqual(result.name, new_experiment_name) 

    # --- Test Cases for get_or_create_assignment ---

    @patch('services.assignment.random.choices')
    def test_get_or_create_assignment_exists_happy_path(self, mock_choices):
        """Tests the happy path when an assignment already exists (READ hit)."""
        
        # Mock the query result to return an existing assignment
        existing_assignment = MockAssignment(user_id='u1', experiment_id=1, variant_name='Control')
        
        self.mock_db.query.return_value.filter.return_value.first.return_value = existing_assignment
        
        # Execute the function
        result = get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=1, user_id='u1')
        
        # Assertions (should return the existing object and not call write methods)
        self.assertEqual(result, existing_assignment)
        self.mock_db.commit.assert_not_called()
        self.mock_db.rollback.assert_not_called()
        mock_choices.assert_not_called()
        
    @patch('services.assignment.random.choices', return_value=['Treatment'])
    def test_get_or_create_assignment_new_creation_happy_path(self, mock_choices):
        """Tests the happy path for creating a new assignment on first attempt (WRITE hit)."""
        
        # 1. Mock the initial READ: No existing assignment
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # 2. Mock the Experiment fetch: Return a valid experiment with variants
        # Note: Since the class is patched at the module level, this returns MockExperiment
        mock_variants = [
            MockVariant(1, 'Control', 50),
            MockVariant(1, 'Treatment', 50)
        ]
        mock_experiment = MockExperiment(id=1, variants=mock_variants)
        self.mock_db.query.return_value.filter.return_value.one_or_none.return_value = mock_experiment

        # 3. Mock the refresh to simulate ID being set after commit
        def mock_refresh(obj):
            obj.id = 500 # Simulate database setting the primary key

        self.mock_db.refresh.side_effect = mock_refresh
        
        # Execute the function
        result = get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=1, user_id='u2')

        # Assertions
        self.assertEqual(result.variant_name, 'Treatment')
        self.assertEqual(result.id, 500)
        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.rollback.assert_not_called()
        
    def test_get_or_create_assignment_experiment_not_found_sad_path(self):
        """Tests the sad path where the experiment is not found (404 HTTPException)."""
        
        # Mock the initial READ: No existing assignment
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock the Experiment fetch: Return None (Experiment not found)
        self.mock_db.query.return_value.filter.return_value.one_or_none.return_value = None

        # Execute and assert HTTPException
        # FIX: The expected error detail must be an exact match of the HTTPException detail raised by the function.
        with self.assertRaisesRegex(HTTPException, "Experiment ID 99 not found or has no variants."):
            get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=99, user_id='u3')
            
        self.mock_db.commit.assert_not_called()
        self.mock_db.rollback.assert_not_called()

    @patch('services.assignment.random.choices', return_value=['Treatment'])
    def test_get_or_create_assignment_race_condition_recovery(self, mock_choices):
        """
        Tests the sad path where a race condition occurs (IntegrityError), 
        and the function successfully recovers on the second attempt (retry).
        """
        
        # 1. Mock the initial READ for the first attempt: No assignment found
        self.mock_db.query.return_value.filter.return_value.first.side_effect = [
            None, # Attempt 1: First check fails (triggers write)
            MockAssignment(user_id='u4', experiment_id=1, variant_name='Control') # Attempt 2: Second check succeeds (reads competing transaction)
        ]

        # 2. Mock the Experiment fetch: Valid experiment
        mock_experiment = MockExperiment(id=1, variants=[MockVariant(1, 'A', 100)])
        self.mock_db.query.return_value.filter.return_value.one_or_none.return_value = mock_experiment

        # 3. Mock the commit: Fail on the first attempt, succeed on the second (not reached)
        self.mock_db.commit.side_effect = [
            IntegrityError("Race", "Params", "Statement"), # Fail commit on Attempt 1
            None # Success on commit (if reached)
        ]
        
        # Execute the function
        result = get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=1, user_id='u4')
        
        # Assertions
        
        # 1. Check final result is the one loaded during the retry read (Control)
        self.assertEqual(result.variant_name, 'Control')
        
        # 2. Commit was called once (failed), rollback was called once (to clear session)
        self.mock_db.commit.assert_called_once()
        self.mock_db.rollback.assert_called_once()
        
        # 3. The loop ran twice (one failed write, one successful read)
        # Assert that query was called 3 times (read, experiment fetch, retry read).
        self.assertEqual(self.mock_db.query.call_count, 3) 

    @patch('services.assignment.random.choices', return_value=['A'])
    def test_get_or_create_assignment_exceeds_max_retries_sad_path(self, mock_choices):
        """
        Tests the sad path where the IntegrityError persists for MAX_RETRIES times.
        """
        
        # 1. Mock the initial READ: Always returns None
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # 2. Mock the Experiment fetch: Valid experiment
        mock_experiment = MockExperiment(id=1, variants=[MockVariant(1, 'A', 100)])
        self.mock_db.query.return_value.filter.return_value.one_or_none.return_value = mock_experiment

        # 3. Mock the commit: Always fail with IntegrityError (for 3 attempts)
        self.mock_db.commit.side_effect = IntegrityError("Race", "Params", "Statement")
        
        # Execute and assert HTTPException
        with self.assertRaisesRegex(HTTPException, "unable to create assignment"):
            get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=1, user_id='u5')
            
        # Assertions
        # Loop runs MAX_RETRIES (3) times, so commit and rollback are called 3 times
        self.assertEqual(self.mock_db.commit.call_count, MAX_RETRIES)
        self.assertEqual(self.mock_db.rollback.call_count, MAX_RETRIES)
        
    @patch('services.assignment.random.choices', return_value=['A'])
    def test_get_or_create_assignment_unexpected_exception_sad_path(self, mock_choices):
        """
        Tests the sad path where a non-IntegrityError Exception occurs.
        """
        
        # 1. Mock the initial READ: Returns None
        self.mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # 2. Mock the Experiment fetch: Valid experiment
        mock_experiment = MockExperiment(id=1, variants=[MockVariant(1, 'A', 100)])
        self.mock_db.query.return_value.filter.return_value.one_or_none.return_value = mock_experiment

        # 3. Mock the commit: Fail with a general exception
        self.mock_db.commit.side_effect = Exception("Database is down")
        
        # Execute and assert HTTPException
        with self.assertRaisesRegex(HTTPException, "unable to create assignment"):
            get_or_create_assignment(self.mock_db, self.mock_cache_client, experiment_id=1, user_id='u6')
            
        # Assertions
        self.mock_db.commit.assert_called_once()
        self.mock_db.rollback.assert_called_once()