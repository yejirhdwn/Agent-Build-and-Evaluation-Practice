package mock.campaign;

import java.util.Map;

/** 캠페인과 고객 대상 조건 데이터를 조회한다. */
public class TargetDao.java {
    private final String component = "TargetDao";

    public int countCandidates(String cmpId) {
        return queryCount("SELECT COUNT(*) FROM CUST_MASTER WHERE cmp_id = ?", cmpId);
    }
    public int countOptOut(String cmpId) {
        return queryCount("SELECT COUNT(*) FROM CONTACT_HIST WHERE consent = 'N' AND cmp_id = ?", cmpId);
    }
    public int countRecentContacts(String cmpId) {
        return queryCount("SELECT COUNT(*) FROM CONTACT_HIST WHERE contact_dt >= ? AND cmp_id = ?", cmpId);
    }
    public void writeTargets(String cmpId, int count) {
        executeUpdate("INSERT INTO CMP_TARGET(cmp_id, target_count) VALUES (?, ?)", cmpId, count);
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

}
