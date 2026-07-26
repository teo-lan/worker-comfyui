import os
import tempfile
import unittest

from src import dream_outbox


class TestDreamOutbox(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = self.temporary_directory.name

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_persist_recover_and_delete(self):
        self.assertTrue(
            dream_outbox.persist(
                "job-123",
                "../scene.png",
                b"generated-image",
                output_index=0,
                root=self.root,
            )
        )
        self.assertTrue(
            dream_outbox.persist(
                "job-123",
                "clip.mp4",
                b"generated-video",
                output_index=1,
                root=self.root,
            )
        )

        recovered = dream_outbox.recover("job-123", root=self.root)

        self.assertEqual(
            [output["filename"] for output in recovered],
            ["scene.png", "clip.mp4"],
        )
        self.assertEqual(
            [output["type"] for output in recovered],
            ["base64", "base64"],
        )
        self.assertEqual(
            dream_outbox.delete(["job-123"], root=self.root),
            ["job-123"],
        )
        self.assertEqual(dream_outbox.recover("job-123", root=self.root), [])

    def test_invalid_job_id_cannot_escape_outbox(self):
        with self.assertRaises(ValueError):
            dream_outbox.persist(
                "../../models",
                "image.png",
                b"unsafe",
                root=self.root,
            )

    def test_prune_only_removes_expired_jobs(self):
        dream_outbox.persist("old-job", "old.png", b"old", root=self.root)
        dream_outbox.persist("fresh-job", "fresh.png", b"fresh", root=self.root)
        old_directory = os.path.join(self.root, "old-job")
        os.utime(old_directory, (100, 100))

        removed = dream_outbox.prune(
            root=self.root,
            now=1_000,
            retention_seconds=500,
        )

        self.assertEqual(removed, ["old-job"])
        self.assertEqual(dream_outbox.recover("old-job", root=self.root), [])
        self.assertEqual(len(dream_outbox.recover("fresh-job", root=self.root)), 1)

    def test_delete_limits_and_validates_acknowledgements(self):
        with self.assertRaises(ValueError):
            dream_outbox.delete("job-123", root=self.root)
        with self.assertRaises(ValueError):
            dream_outbox.delete(["../job-123"], root=self.root)


if __name__ == "__main__":
    unittest.main()
