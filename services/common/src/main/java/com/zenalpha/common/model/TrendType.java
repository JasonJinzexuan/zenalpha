package com.zenalpha.common.model;

import com.zenalpha.common.enums.TrendClass;
import com.zenalpha.common.enums.TimeFrame;

import java.util.List;

public record TrendType(
        TrendClass classification,
        List<Center> centers,
        TimeFrame level,
        Segment segmentA,
        Center centerA,
        Segment segmentB,
        Center centerB,
        Segment segmentC
) {
}
