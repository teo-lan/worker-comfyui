import pathlib
import unittest


class TestVideoTransitionNode(unittest.TestCase):
    def test_first_last_frame_node_is_pinned_before_comfyui_smoke_test(self):
        dockerfile = (pathlib.Path(__file__).parents[1] / "Dockerfile").read_text()
        repository = "stduhpf/ComfyUI--Wan22FirstLastFrameToVideoLatent"
        commit = "caa90f0d5e2e33cbe7761fc18553d07e1d30d1ff"

        self.assertIn(repository, dockerfile)
        self.assertIn(commit, dockerfile)
        self.assertLess(
            dockerfile.index(repository),
            dockerfile.index("--quick-test-for-ci"),
        )


if __name__ == "__main__":
    unittest.main()
