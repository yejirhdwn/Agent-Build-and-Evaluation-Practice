package mock.campaign;


/** 할당된 오퍼에서 채널 발송 요청을 생성한다. */
public class MessageBuildJob.java {
    private final String component = "MessageBuildJob";

    public int build(String cmpId) {
        int offers = messageDao.countOffers(cmpId);
        int requests = messageDao.renderTemplate(cmpId);
        if (offers != requests) {
            throw new IllegalStateException("MESSAGE_COUNT_MISMATCH");
        }
        return requests;
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
