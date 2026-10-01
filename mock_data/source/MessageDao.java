package mock.campaign;


/** 할당된 오퍼를 조회하고 채널 요청을 기록한다. */
public class MessageDao.java {
    private final String component = "MessageDao";

    public int countOffers(String cmpId) {
        return queryCount("SELECT COUNT(*) FROM CMP_OFFER WHERE cmp_id = ?", cmpId);
    }
    public int renderTemplate(String cmpId) {
        return executeUpdate("INSERT INTO CHNL_SEND_REQ SELECT * FROM CMP_OFFER WHERE cmp_id = ?", cmpId);
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
