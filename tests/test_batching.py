from unittest import TestCase

from lambda_function import Batcher


class BatchingSuite(TestCase):

    def setUp(self):
        self.batcher = Batcher(1024)

    def test_no_batching_needed(self):
        items = ["x" * 128, "y" * 512, "z" * 384]
        batches = self.batcher.batch(items)
        self.assertEqual(1, len(batches))
        self.assertEqual(items, batches[0])

    def test_batching(self):
        items = ["x" * 512, "y" * 256, "z" * 1024, "a" * 64]
        batches = self.batcher.batch(items)
        self.assertEqual(3, len(batches))
        self.assertEqual([items[0], items[1]], batches[0])
        self.assertEqual([items[2]], batches[1])
        self.assertEqual([items[3]], batches[2])

    def test_truncate_if_item_is_too_big(self):
        items = ["x" * 2048]
        batches = self.batcher.batch(items)
        self.assertEqual(1, len(batches))
        self.assertEqual(["x" * 1024], batches[0])