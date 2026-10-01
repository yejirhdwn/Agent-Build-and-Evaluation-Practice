package mock.campaign;

import java.sql.Connection;
import java.time.LocalDate;
import java.util.List;

/** 캠페인 하나를 단일 트랜잭션으로 발송한다. */
public class ChannelSendJob.java {
    private final String component = "ChannelSendJob";

    public void runCampaign(String cmpId) {
        Connection connection = dataSource.begin();
        try {
            connection.setAutoCommit(false);
            List<Request> requests = sendDao.findRequests(connection, cmpId);
            for (Request request : requests) {
                sendDao.insertRelayOut(connection, request);
                sendDao.insertSendHistory(connection, request, "REQ");
            }
            validator.validate(campaignDao.findSendDate(cmpId), LocalDate.now());
            connection.commit();
        } catch (RuntimeException error) {
            connection.rollback();
            logger.warn("Transaction rolled back. cmp_id={} rolled_back={}", cmpId, requests.size());
            throw error;
        } finally {
            connection.close();
        }
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

}
