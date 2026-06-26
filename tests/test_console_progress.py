from __future__ import annotations

import io
import time
import unittest

from questiongen.batch import BatchProgressUpdate
from questiongen.console_progress import ConsoleProgressRenderer


class _TTYBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


class ConsoleProgressRendererTests(unittest.TestCase):
    def test_live_renderer_starts_and_stops_with_final_completion_line(self) -> None:
        stream = _TTYBuffer()
        renderer = ConsoleProgressRenderer(
            stream=stream,
            heartbeat_interval_seconds=0.01,
            live_updates=True,
        )

        renderer.start()
        renderer.callback(
            BatchProgressUpdate(
                event="started",
                completed_items=0,
                total_items=1,
                message="Starting batch run.",
            )
        )
        renderer.callback(
            BatchProgressUpdate(
                event="item_started",
                completed_items=0,
                total_items=1,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="sentence_insertion",
                question_subtype_key="sentence_insertion_basic",
                status="running",
            )
        )
        time.sleep(0.03)
        renderer.callback(
            BatchProgressUpdate(
                event="item_completed",
                completed_items=1,
                total_items=1,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="sentence_insertion",
                question_subtype_key="sentence_insertion_basic",
                status="validation_passed",
            )
        )
        renderer.callback(
            BatchProgressUpdate(
                event="completed",
                completed_items=1,
                total_items=1,
                message="Completed batch run with 1 exported rows.",
            )
        )
        renderer.stop(success=True)

        output = stream.getvalue()
        self.assertIn("\r", output)
        self.assertIn("done 1/1 | 10-03 | sentence_insertion_basic | Completed batch run with 1 exported rows.", output)

    def test_notable_messages_print_above_live_spinner_line(self) -> None:
        stream = _TTYBuffer()
        renderer = ConsoleProgressRenderer(
            stream=stream,
            heartbeat_interval_seconds=0.01,
            live_updates=True,
        )

        renderer.start()
        renderer.callback(
            BatchProgressUpdate(
                event="item_started",
                completed_items=0,
                total_items=2,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="paragraph_ordering",
                question_subtype_key="paragraph_ordering_4_blocks",
                status="running",
            )
        )
        renderer.callback(
            BatchProgressUpdate(
                event="item_completed",
                completed_items=1,
                total_items=2,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="paragraph_ordering",
                question_subtype_key="paragraph_ordering_4_blocks",
                status="planning_error",
                message="Planner returned invalid block ordering.",
            )
        )
        renderer.stop(success=False, message="Run failed: planning_error")

        output = stream.getvalue()
        self.assertIn(
            "[1/2] 10-03 :: paragraph_ordering_4_blocks -> planning_error | Planner returned invalid block ordering.\n",
            output,
        )
        self.assertIn("failed 1/2 | 10-03 | paragraph_ordering_4_blocks | Run failed: planning_error", output)

    def test_validation_passed_updates_do_not_create_stable_log_lines(self) -> None:
        stream = io.StringIO()
        renderer = ConsoleProgressRenderer(stream=stream, live_updates=False)

        renderer.start()
        renderer.callback(
            BatchProgressUpdate(
                event="item_completed",
                completed_items=1,
                total_items=1,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="sentence_insertion",
                question_subtype_key="sentence_insertion_basic",
                status="validation_passed",
            )
        )
        renderer.callback(
            BatchProgressUpdate(
                event="completed",
                completed_items=1,
                total_items=1,
                message="Completed batch run with 1 exported rows.",
            )
        )
        renderer.stop(success=True)

        output = stream.getvalue()
        self.assertNotIn("[1/1] 10-03 :: sentence_insertion_basic -> validation_passed", output)
        self.assertIn("Completed batch run with 1 exported rows.", output)

    def test_failure_stop_prints_final_line_in_non_live_mode(self) -> None:
        stream = io.StringIO()
        renderer = ConsoleProgressRenderer(stream=stream, live_updates=False)

        renderer.start()
        renderer.callback(
            BatchProgressUpdate(
                event="item_started",
                completed_items=0,
                total_items=2,
                current_row_number="10-03",
                batch_row_id=0,
                question_type_key="sentence_insertion",
                question_subtype_key="sentence_insertion_basic",
                status="running",
            )
        )
        renderer.stop(success=False, message="Run failed: network timeout")

        output = stream.getvalue()
        self.assertIn("failed 0/2 | 10-03 | sentence_insertion_basic | Run failed: network timeout", output)


if __name__ == "__main__":
    unittest.main()
