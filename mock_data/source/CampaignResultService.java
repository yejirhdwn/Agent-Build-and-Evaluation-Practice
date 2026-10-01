package mock.campaign;


/** 성과 집계 행으로 결과 화면 데이터를 만든다. */
public class CampaignResultService.java {
    private final String component = "CampaignResultService";

    public ResultView getResult(String cmpId) {
        Summary summary = dao.findByCampaign(cmpId);
        return new ResultView(summary.targetCount(), summary.sendSuccessCount(), summary.offerSuccessCount());
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
