"""
Tests for RLTrainer.

Test suite for RL training orchestration:
    - Initialization
    - Walk-forward training
    - Environment creation
    - Agent creation
    - Date splitting
    - Baseline comparisons
    - Results saving

Coverage Target: 75%+
"""

import pytest
import pandas as pd
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from financial_analyzer.rl.trainers import RLTrainer


class TestRLTrainerInit:
    """Test RLTrainer initialization."""
    
    def test_init_basic(self):
        """Test basic initialization."""
        trainer = RLTrainer(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        assert len(trainer.symbols) == 2
        assert trainer.start_date == '2020-01-01'
        assert trainer.end_date == '2023-12-31'
        assert trainer.initial_capital == 100_000
    
    def test_init_custom_capital(self):
        """Test initialization with custom capital."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31',
            initial_capital=500_000
        )
        
        assert trainer.initial_capital == 500_000
    
    def test_init_custom_splits(self):
        """Test initialization with custom train/val/test splits."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31',
            train_ratio=0.6,
            val_ratio=0.2,
            test_ratio=0.2
        )
        
        assert trainer.train_ratio == 0.6
        assert trainer.val_ratio == 0.2
        assert trainer.test_ratio == 0.2
    
    def test_init_creates_directories(self):
        """Test initialization creates model and log directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2023-12-31',
                models_dir=f"{tmpdir}/models",
                logs_dir=f"{tmpdir}/logs"
            )
            
            assert trainer.models_dir.exists()
            assert trainer.logs_dir.exists()


class TestRLTrainerDateSplitting:
    """Test date splitting functionality."""
    
    def test_split_dates_basic(self):
        """Test basic date splitting."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-12-31',
            train_ratio=0.7,
            val_ratio=0.15,
            test_ratio=0.15
        )
        
        train_start, train_end, val_start, val_end, test_start, test_end = (
            trainer._split_dates()
        )
        
        assert train_start == '2020-01-01'
        assert test_end == '2020-12-31'
        # Validate date order
        assert pd.to_datetime(train_end) < pd.to_datetime(val_start)
        assert pd.to_datetime(val_end) < pd.to_datetime(test_start)
    
    def test_split_dates_proportions(self):
        """Test date splits respect proportions."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31',  # 4 years
            train_ratio=0.5,
            val_ratio=0.25,
            test_ratio=0.25
        )
        
        train_start, train_end, val_start, val_end, test_start, test_end = (
            trainer._split_dates()
        )
        
        # Check approximate proportions
        total_days = (pd.to_datetime('2023-12-31') - pd.to_datetime('2020-01-01')).days
        train_days = (pd.to_datetime(train_end) - pd.to_datetime(train_start)).days
        
        # Should be roughly 50% (allowing some tolerance)
        assert 0.45 < train_days / total_days < 0.55


class TestRLTrainerEnvironmentCreation:
    """Test environment creation."""
    
    def test_create_environment_basic(self):
        """Test basic environment creation."""
        trainer = RLTrainer(
            symbols=['AAPL', 'MSFT'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        env = trainer._create_environment('2020-01-01', '2020-06-30')
        
        assert env is not None
        assert env.n_assets == 2
    
    def test_create_environment_uses_settings(self):
        """Test environment creation uses trainer settings."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31',
            initial_capital=200_000
        )
        
        env = trainer._create_environment('2020-01-01', '2020-06-30')
        
        assert env.initial_capital == 200_000


class TestRLTrainerAgentCreation:
    """Test agent creation."""
    
    def test_create_agent_ppo(self):
        """Test PPO agent creation."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        env = trainer._create_environment('2020-01-01', '2020-06-30')
        agent = trainer._create_agent('ppo', env)
        
        assert agent is not None
    
    def test_create_agent_invalid_type(self):
        """Test agent creation with invalid type."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        env = trainer._create_environment('2020-01-01', '2020-06-30')
        
        with pytest.raises(ValueError):
            trainer._create_agent('invalid_type', env)
    
    def test_create_agent_with_kwargs(self):
        """Test agent creation with custom kwargs."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        env = trainer._create_environment('2020-01-01', '2020-06-30')
        agent = trainer._create_agent(
            'ppo',
            env,
            agent_kwargs={'learning_rate': 1e-3}
        )
        
        assert agent.learning_rate == 1e-3


class TestRLTrainerTraining:
    """Test training functionality (integration tests)."""
    
    @pytest.mark.slow
    def test_train_walk_forward_basic(self):
        """Test basic walk-forward training (very short)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',  # Short period
                models_dir=tmpdir,
                logs_dir=tmpdir
            )
            
            results = trainer.train_walk_forward(
                agent_type='ppo',
                total_timesteps=100,  # Very short for speed
                eval_freq=50,
                save_freq=50
            )
            
            assert isinstance(results, dict)
            assert 'agent_type' in results
            assert 'test_metrics' in results
            assert results['agent_type'] == 'ppo'
    
    @pytest.mark.slow
    def test_train_stores_results(self):
        """Test training stores results in trainer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',
                models_dir=tmpdir
            )
            
            trainer.train_walk_forward(
                agent_type='ppo',
                total_timesteps=100
            )
            
            assert 'ppo' in trainer.training_results
            assert isinstance(trainer.training_results['ppo'], dict)


class TestRLTrainerBaselines:
    """Test baseline comparison functionality."""
    
    def test_compare_baselines_structure(self):
        """Test baseline comparison returns proper structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',
                models_dir=tmpdir
            )
            
            # Mock results
            mock_results = {
                'agent_type': 'ppo',
                'test_period': ('2020-05-01', '2020-06-30'),
                'test_metrics': {
                    'mean_reward': 1.5,
                    'std_reward': 0.3
                }
            }
            
            comparison = trainer.compare_baselines(mock_results)
            
            assert isinstance(comparison, pd.DataFrame)
            assert 'mean_reward' in comparison.columns
            assert 'RL Agent' in comparison.index
    
    def test_compare_baselines_no_results(self):
        """Test baseline comparison with no training results."""
        trainer = RLTrainer(
            symbols=['AAPL'],
            start_date='2020-01-01',
            end_date='2020-06-30'
        )
        
        comparison = trainer.compare_baselines()
        
        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) == 0


class TestRLTrainerSaveLoad:
    """Test save/load functionality."""
    
    def test_save_results_basic(self):
        """Test basic results saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',
                models_dir=tmpdir
            )
            
            # Add mock results
            trainer.training_results['ppo'] = {
                'agent_type': 'ppo',
                'train_period': ('2020-01-01', '2020-03-31'),
                'val_period': ('2020-04-01', '2020-05-15'),
                'test_period': ('2020-05-16', '2020-06-30'),
                'test_metrics': {'mean_reward': 1.5},
                'model_path': None
            }
            
            trainer.save_results('test_results.json')
            
            result_file = Path(tmpdir) / 'test_results.json'
            assert result_file.exists()
    
    def test_save_results_auto_filename(self):
        """Test results saving with auto-generated filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',
                models_dir=tmpdir
            )
            
            # Add mock results
            trainer.training_results['ppo'] = {
                'agent_type': 'ppo',
                'train_period': ('2020-01-01', '2020-03-31'),
                'val_period': ('2020-04-01', '2020-05-15'),
                'test_period': ('2020-05-16', '2020-06-30'),
                'test_metrics': {'mean_reward': 1.5},
                'model_path': None
            }
            
            trainer.save_results()
            
            # Check a file was created
            result_files = list(Path(tmpdir).glob('rl_results_*.json'))
            assert len(result_files) == 1


class TestRLTrainerRepr:
    """Test string representation."""
    
    def test_repr(self):
        """Test string representation."""
        trainer = RLTrainer(
            symbols=['AAPL', 'MSFT', 'GOOGL'],
            start_date='2020-01-01',
            end_date='2023-12-31'
        )
        
        repr_str = repr(trainer)
        
        assert 'RLTrainer' in repr_str
        assert '3' in repr_str or 'AAPL' in repr_str
        assert '2020-01-01' in repr_str
        assert '2023-12-31' in repr_str


class TestRLTrainerEdgeCases:
    """Test edge cases and error handling."""
    
    def test_train_with_invalid_agent_type(self):
        """Test training with invalid agent type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = RLTrainer(
                symbols=['AAPL'],
                start_date='2020-01-01',
                end_date='2020-06-30',
                models_dir=tmpdir
            )
            
            with pytest.raises(ValueError):
                trainer.train_walk_forward(
                    agent_type='invalid_agent',
                    total_timesteps=100
                )
    
    def test_empty_symbols_list(self):
        """Test initialization with empty symbols."""
        # Should initialize but may fail on environment creation
        trainer = RLTrainer(
            symbols=[],
            start_date='2020-01-01',
            end_date='2020-06-30'
        )
        
        assert len(trainer.symbols) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
