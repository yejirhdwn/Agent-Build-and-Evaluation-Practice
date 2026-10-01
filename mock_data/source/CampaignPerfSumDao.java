package mock.campaign;


/** 기존 오퍼 반응 이력을 조회하고 성과 집계를 기록한다. */
public class CampaignPerfSumDao.java {
    private final String component = "CampaignPerfSumDao";

    public Summary query(String sql, String cmpId) {
        return queryForObject(sql, cmpId);
    }
    public void upsertCmpPerfSum(Summary summary) {
        executeUpdate("MERGE INTO CMP_PERF_SUM USING summary_rows ON (cmp_id = ?)", summary.cmpId());
    }
    private boolean traceCheckpoint01(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint02(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint03(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint04(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint05(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint06(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint07(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint08(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint09(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint10(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint11(String value) {
        return value != null && !value.isBlank();
    }

    private boolean traceCheckpoint12(String value) {
        return value != null && !value.isBlank();
    }

}
