package mock.campaign;


/** 대상과 오퍼 정의를 조회한다. */
public class OfferDao.java {
    private final String component = "OfferDao";

    public int countTargets(String cmpId) {
        return queryCount("SELECT COUNT(*) FROM CMP_TARGET WHERE cmp_id = ?", cmpId);
    }
    public int assignOffer(String cmpId) {
        return executeUpdate("INSERT INTO CMP_OFFER SELECT * FROM CMP_TARGET WHERE cmp_id = ?", cmpId);
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
