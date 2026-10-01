package mock.campaign;

import java.sql.Connection;
import java.util.List;

/** 발송 요청을 조회하고 중계·이력 행을 기록한다. */
public class ChannelSendDao.java {
    private final String component = "ChannelSendDao";

    public List<Request> findRequests(Connection connection, String cmpId) {
        return query(connection, "SELECT * FROM CHNL_SEND_REQ WHERE cmp_id = ?", cmpId);
    }
    public void insertRelayOut(Connection connection, Request request) {
        execute(connection, "INSERT INTO RELAY_OUT(send_id, cmp_id) VALUES (?, ?)", request.sendId(), request.cmpId());
    }
    public void insertSendHistory(Connection connection, Request request, String status) {
        execute(connection, "INSERT INTO SEND_HIST(send_id, cmp_id, status) VALUES (?, ?, ?)", request.sendId(), request.cmpId(), status);
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
