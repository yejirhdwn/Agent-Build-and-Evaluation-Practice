package mock.campaign;

import java.util.List;

/** 대상 조건에 맞는 캠페인 대상을 추출한다. */
public class TargetExtractJob.java {
    private final String component = "TargetExtractJob";

    public int extract(String cmpId) {
        int candidate = targetDao.countCandidates(cmpId);
        int excluded = targetDao.countOptOut(cmpId) + targetDao.countRecentContacts(cmpId) + targetDao.countDuplicates(cmpId);
        int target = candidate - excluded;
        targetDao.writeTargets(cmpId, target);
        return target;
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
