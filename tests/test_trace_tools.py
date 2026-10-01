import unittest

from trace_tools import (
    build_trace_tools,
    get_batch_jobs,
    get_change_log,
    get_module_relations,
    query_campaign,
    query_perf_summary,
    query_send_history,
    query_table_status,
    read_source,
    search_incident_history,
    search_source,
)


class TraceToolsTest(unittest.TestCase):
    def test_scenario_campaign_and_send_history(self):
        campaign = query_campaign.invoke({"campaign_id": "20260923CMP001"})
        self.assertEqual(campaign["send_dt"], "2026-09-23")

        history = query_send_history.invoke(
            {"campaign_id": "20260923CMP002", "status": "SUCC"}
        )
        self.assertEqual(history["summary"][0]["count"], 2)

    def test_scenario_relations_source_and_summary(self):
        relations = get_module_relations.invoke({"query": "OFFER_RESULT"})
        self.assertTrue(any(row["from"] == "ResultReceiveJob" for row in relations))

        source = search_source.invoke({"keyword": "OFFER_RESP_HIST"})
        self.assertTrue(any(row["source_file"] == "CampaignPerfSumJob.java" for row in source))

        summary = query_perf_summary.invoke({"campaign_id": "20260924CMP001"})
        self.assertEqual(summary["offer_success_count"], "0")

    def test_scenario_target_exclusions_and_source_lines(self):
        source = read_source.invoke(
            {"class_name": "ChannelSendJob", "start_line": 20, "end_line": 25}
        )
        self.assertTrue(any("rollback" in line for line in source["numbered_source"]))

        jobs = get_batch_jobs.invoke({"job_id": "B01_TARGET"})
        self.assertEqual(jobs[0]["main_class"], "TargetExtractJob")

    def test_scenario_missing_evidence_returns_message(self):
        incidents = search_incident_history.invoke({"keyword": "does-not-exist"})
        self.assertIn("없습니다", incidents["message"])

        status = query_table_status.invoke(
            {"table_name": "OFFER_RESP_HIST", "start_date": "2026-09-24", "end_date": "2026-09-26"}
        )
        self.assertIn("없습니다", status["message"])

    def test_change_log_and_eval_are_not_readable(self):
        changes = get_change_log.invoke(
            {"start_date": "2026-09-24", "end_date": "2026-09-24"}
        )
        self.assertEqual(changes[0]["object"], "offer response storage")

        self.assertIn("찾지 못했습니다", search_source.invoke({"keyword": "eval/answer_keys/S1.md"})["message"])
        self.assertIn("찾을 수 없습니다", read_source.invoke({"class_name": "../eval/answer_keys/S1.md"})["message"])

    def test_tools_are_read_only_and_registered(self):
        names = {tool.name for tool in build_trace_tools()}
        self.assertEqual(
            names,
            {
                "query_send_history",
                "get_batch_jobs",
                "get_module_relations",
                "read_source",
                "search_source",
                "search_incident_history",
                "query_campaign",
                "query_table_status",
                "query_perf_summary",
                "get_change_log",
            },
        )
        self.assertIn("1에서 100", query_send_history.invoke({"limit": 101})["message"])


if __name__ == "__main__":
    unittest.main()
