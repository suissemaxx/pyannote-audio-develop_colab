# MIT License
#
# Copyright (c) 2020-2021 CNRS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from .segmentation.voice_activity_detection import VoiceActivityDetection  # isort:skip
from .segmentation.speaker_change_detection import SpeakerChangeDetection  # isort:skip
from .segmentation.overlapped_speech_detection import (  # isort:skip
    OverlappedSpeechDetection,
)

from .segmentation.speaker_tracking import SpeakerTracking  # isort:skip

from .segmentation.segmentation import Segmentation  # isort:skip

from .embedding.arcface import SupervisedRepresentationLearningWithArcFace  # isort:skip

SpeakerEmbedding = SupervisedRepresentationLearningWithArcFace

__all__ = [
    "Segmentation",
    "VoiceActivityDetection",
    "SpeakerChangeDetection",
    "OverlappedSpeechDetection",
    "SpeakerTracking",
    "SpeakerEmbedding",
]
