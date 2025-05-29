"""
Store metrics used to benchmark eviction algorithms
"""

class EvictionMetrics:
    def __init__(self, metric_dict: dict=None):
        """
        Initialize the metrics with a dictionary.
        """
        if metric_dict:
            self._hits = metric_dict["hits"]
            self._misses = metric_dict["misses"]
            self._sets = metric_dict["sets"]
            self._n_evicts = metric_dict["n_evicts"]
            self._n_reuse_evicts = metric_dict["n_reuse_evicts"]
    
    def hit_ratio(self, hits: int=None, misses: int=None) -> float:
        """
        Cachine Effectiveness
        """
        if self._hits is not None:
            return self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0.0
        return hits / (hits + misses) if (hits + misses) > 0 else 0.0
    
    def accuracy(self, n_reuse_evicts: int=None, n_evicts: int=None) -> float:
        """
        Classification Accuracy
        """
        if self._n_evicts is not None:
            return (self._n_evicts - self._n_reuse_evicts) / self._n_evicts if self._n_evicts > 0 else 0.0
        return (n_evicts - n_reuse_evicts) / n_evicts if n_evicts > 0 else 0.0
    
    def latency(self, total_time: float=None) -> float:
        """
        Benchmarking Latency
        """
        return total_time