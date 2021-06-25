# The MIT License (MIT)
#
# Copyright (c) 2018-2021 CNRS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Overlapped speech detection pipelines"""

from typing import Optional

import numpy as np

from pyannote.audio import Inference
from pyannote.audio.core.io import AudioFile
from pyannote.audio.core.pipeline import Pipeline
from pyannote.audio.pipelines.utils import PipelineModel, get_devices, get_model
from pyannote.audio.utils.signal import Binarize
from pyannote.core import Annotation, Timeline
from pyannote.database import get_annotated
from pyannote.metrics.detection import DetectionPrecisionRecallFMeasure
from pyannote.pipeline.parameter import Uniform


def to_overlap(annotation: Annotation) -> Annotation:
    """Get overlapped speech regions

    Parameters
    ----------
    annotation : Annotation
        Speaker annotation.

    Returns
    -------
    overlap : Annotation
        Overlapped speech annotation.
    """

    overlap = Timeline(uri=annotation.uri)
    for (s1, t1), (s2, t2) in annotation.co_iter(annotation):
        l1 = annotation[s1, t1]
        l2 = annotation[s2, t2]
        if l1 == l2:
            continue
        overlap.add(s1 & s2)
    return overlap.support().to_annotation(generator="string", modality="overlap")


class OracleOverlappedSpeechDetection(Pipeline):
    """Oracle overlapped speech detection pipeline"""

    def apply(self, file: AudioFile) -> Annotation:
        """Return groundtruth overlapped speech detection

        Parameter
        ---------
        file : AudioFile
            Must provide a "annotation" key.

        Returns
        -------
        hypothesis : Annotation
            Overlapped speech regions.
        """
        return to_overlap(file["annotation"])


class OverlappedSpeechDetection(Pipeline):
    """Overlapped speech detection pipeline

    Parameters
    ----------
    segmentation : Model, str, or dict, optional
        Pretrained segmentation (or overlapped speech detection) model.
        Defaults to "pyannote/segmentation".
        See pyannote.audio.pipelines.utils.get_model for supported format.
    precision : float, optional
        Optimize recall at target precision.
        Defaults to optimize precision/recall fscore.
    recall : float, optional
        Optimize precision at target recall
        Defaults to optimize precision/recall fscore
    inference_kwargs : dict, optional
        Keywords arguments passed to Inference.

    Hyper-parameters
    ----------------
    onset, offset : float
        Onset/offset detection thresholds
    min_duration_on : float
        Remove speech regions shorter than that many seconds.
    min_duration_off : float
        Fill non-speech regions shorter than that many seconds.
    """

    def __init__(
        self,
        segmentation: PipelineModel = "pyannote/segmentation",
        precision: Optional[float] = None,
        recall: Optional[float] = None,
        **inference_kwargs,
    ):
        super().__init__()

        self.segmentation = segmentation

        # load model and send it to GPU (when available and not already on GPU)
        model = get_model(segmentation)
        if model.device.type == "cpu":
            (segmentation_device,) = get_devices(needs=1)
            model.to(segmentation_device)

        if model.introspection.dimension > 1:
            inference_kwargs["pre_aggregation_hook"] = lambda scores: np.partition(
                scores, -2, axis=-1
            )[:, :, -2, np.newaxis]
        self.segmentation_inference_ = Inference(model, **inference_kwargs)

        #  hyper-parameters used for hysteresis thresholding
        self.onset = Uniform(0.0, 1.0)
        self.offset = Uniform(0.0, 1.0)

        # hyper-parameters used for post-processing i.e. removing short overlapped regions
        # or filling short gaps between overlapped regions
        self.min_duration_on = Uniform(0.0, 1.0)
        self.min_duration_off = Uniform(0.0, 1.0)

        if (precision is not None) and (recall is not None):
            raise ValueError(
                "One must choose between optimizing for target precision or target recall."
            )

        self.precision = precision
        self.recall = recall

    def initialize(self):
        """Initialize pipeline with current set of parameters"""

        self._binarize = Binarize(
            onset=self.onset,
            offset=self.offset,
            min_duration_on=self.min_duration_on,
            min_duration_off=self.min_duration_off,
        )

    def apply(self, file: AudioFile) -> Annotation:
        """Apply overlapped speech detection

        Parameters
        ----------
        file : AudioFile
            Processed file.

        Returns
        -------
        overlapped_speech : `pyannote.core.Annotation`
            Overlapped speech regions.
        """

        activation = self.segmentation_inference_(file)
        file["@overlapped_speech_detection/activation"] = activation

        overlapped_speech = self._binarize(activation)
        overlapped_speech.uri = file["uri"]
        return overlapped_speech

    def get_metric(self, **kwargs) -> DetectionPrecisionRecallFMeasure:
        """Get overlapped speech detection metric

        Returns
        -------
        metric : DetectionPrecisionRecallFMeasure
            Detection metric.
        """

        if (self.precision is not None) or (self.recall is not None):
            raise NotImplementedError(
                "pyannote.pipeline should use `loss` method fallback."
            )

        class _Metric(DetectionPrecisionRecallFMeasure):
            def compute_components(
                _self,
                reference: Annotation,
                hypothesis: Annotation,
                uem: Timeline = None,
                **kwargs,
            ) -> dict:
                return super().compute_components(
                    to_overlap(reference), hypothesis, uem=uem, **kwargs
                )

        return _Metric()

    def loss(self, file: AudioFile, hypothesis: Annotation) -> float:
        """Compute recall at target precision (or vice versa)

        Parameters
        ----------
        file : AudioFile
            Processed file.
        hypothesis : Annotation
            Hypothesized overlapped speech regions.

        Returns
        -------
        recall (or purity) : float
            When optimizing for target precision:
                If precision < target_precision, returns (precision - target_precision).
                If precision > target_precision, returns recall.
            When optimizing for target recall:
                If recall < target_recall, returns (recall - target_recall).
                If recall > target_recall, returns precision.
        """

        fmeasure = DetectionPrecisionRecallFMeasure()

        if "overlap_reference" in file:
            overlap_reference = file["overlap_reference"]

        else:
            reference = file["annotation"]
            overlap_reference = to_overlap(reference)
            file["overlap_reference"] = overlap_reference

        _ = fmeasure(overlap_reference, hypothesis, uem=get_annotated(file))
        precision, recall, _ = fmeasure.compute_metrics()

        if self.precision is not None:
            if precision < self.precision:
                return precision - self.precision
            else:
                return recall

        elif self.recall is not None:
            if recall < self.recall:
                return recall - self.recall
            else:
                return precision

    def get_direction(self):
        return "maximize"
