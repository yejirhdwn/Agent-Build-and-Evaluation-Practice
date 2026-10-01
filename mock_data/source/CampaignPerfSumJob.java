package mock.campaign;


/** 결과 화면용 캠페인 성과 지표를 집계한다. */
public class CampaignPerfSumJob.java {
    private final String component = "CampaignPerfSumJob";

    private static final String SQL =
        "SELECT s.cmp_id, COUNT(DISTINCT s.send_id), COUNT(DISTINCT o.cust_id) " +
        "FROM SEND_HIST s LEFT JOIN OFFER_RESP_HIST o ON o.cmp_id = s.cmp_id " +
        "WHERE s.cmp_id = ? GROUP BY s.cmp_id";

    public void aggregate(String cmpId) {
        Summary summary = perfDao.query(SQL, cmpId);
        perfDao.upsertCmpPerfSum(summary);
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

}
