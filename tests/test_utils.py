from __future__ import annotations

import unittest

import pytest

from compass_lib.utils import OrderedQueue


class TestOrderedQueue(unittest.TestCase):
    """Unit tests for OrderedQueue."""

    def setUp(self):
        self.ordered_queue = OrderedQueue()

    def test_add_new_key(self):
        """
        Tests adding a new key to the ordered queue.
        """
        self.ordered_queue.add("new_key", value=123)
        assert "new_key" in self.ordered_queue
        assert self.ordered_queue["new_key"] == 123

    def test_add_duplicate_key(self):
        """
        Tests adding an existing key to the ordered queue.
        The key should not be added again.
        """
        self.ordered_queue.add("existing_key", value=1)
        assert self.ordered_queue["existing_key"] == 1
        with pytest.raises(KeyError):
            self.ordered_queue.add("existing_key", value=2, fail_if_present=True)

        self.ordered_queue.add("existing_key", value=2, fail_if_present=False)
        assert self.ordered_queue["existing_key"] == 2

    def test_remove_key(self):
        """
        Tests removing a key from the ordered queue.
        """
        self.ordered_queue.add("key_to_remove", value=None)
        self.ordered_queue.remove("key_to_remove")
        with pytest.raises(KeyError):
            self.ordered_queue["key_to_remove"]

    def test_remove_nonexistent_key(self):
        """
        Tests trying to remove a non-existent key from the ordered queue.
        A KeyError should be raised.
        """
        with pytest.raises(KeyError):
            self.ordered_queue.remove("nonexistent_key")

    def test_iter_keys(self):
        """
        Tests iterating over the keys in the ordered queue.
        The order of iteration should match the insertion order.
        """
        for i in range(4, 0, -1):
            self.ordered_queue.add(f"key_{i}", value=None)

        assert list(self.ordered_queue.keys()) == ["key_4", "key_3", "key_2", "key_1"]

    def test_len(self):
        """
        Tests the length of the ordered queue.
        The length should match the number of keys in the dictionary.
        """
        for i in range(5):
            self.ordered_queue.add(f"key_{i}", value=None)
        assert len(self.ordered_queue) == 5


if __name__ == "__main__":
    unittest.main()
