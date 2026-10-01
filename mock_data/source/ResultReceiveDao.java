package mock.campaign;

import java.util.List;

/** 발송 이력을 갱신하고 새 오퍼 반응 테이블에 기록한다. */
public class ResultReceiveDao.java {
    private final String component = "ResultReceiveDao";

    public int updateSendHistory(String cmpId, List<ResultRow> rows) {
        return batchUpdate("UPDATE SEND_HIST SET status = ? WHERE cmp_id = ? AND send_id = ?", cmpId, rows);
    }
    public int mergeOfferResults(String cmpId, List<ResultRow> rows) {
        return batchUpdate("MERGE INTO OFFER_RESULT USING response_rows ON (cmp_id = ?)", cmpId, rows);
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
