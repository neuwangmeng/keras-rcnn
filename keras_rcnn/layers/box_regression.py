import keras.engine.topology
import keras.backend
import keras_rcnn.backend
import keras_rcnn.layers.object_detection._object_proposal

class BoxRegression(keras.engine.topology.Layer):
    """
    Get final detections + labels by unscaling back to image space, performing box regression, choosing box coordinates, and removing extra detections via NMS
    """
    def __init__(self, threshold = 0.05, test_nms = 0.5, **kwargs):
        self.threshold = threshold

        self.TEST_NMS = test_nms

        super(BoxRegression, self).__init__(**kwargs)

    def build(self, input_shape):

        super(BoxRegression, self).build(input_shape)

    def call(self, x, **kwargs):
        """
        rois: output of proposal target (1, N, 4)
        pred_boxes: box predictions (1, N, 4*classes)
        pred_scores: score distributions (1, N, classes)
        metadata: image information (1, 3)
        """
        rois, pred_boxes, pred_scores, metadata = x[0], x[1], x[2], x[3]
        rois = rois[0, :, :]
        pred_boxes = pred_boxes[0, :, :]
        pred_scores = pred_scores[0, :, :]

        # unscale back to raw image space

        boxes = rois / metadata[0][2]

        # Apply bounding-box regression deltas

        pred_boxes = keras_rcnn.layers.object_detection._object_proposal.bbox_transform_inv(boxes, pred_boxes)
        pred_boxes = keras_rcnn.backend.clip(pred_boxes, metadata[0][:2])

        # Final detections

        # keep detections above threshold
        indices_threshold = keras_rcnn.backend.where(keras.backend.greater(pred_scores, self.threshold))
        pred_scores = keras_rcnn.backend.gather_nd(pred_scores, indices_threshold)
        pred_boxes = keras_rcnn.backend.gather_nd(pred_boxes, indices_threshold)

        # for each object, get the top class score and corresponding bbox, apply nms
        pred_classes = keras.backend.argmax(pred_scores, axis=1)

        indices = keras.backend.arange(0, keras.backend.shape(pred_scores)[0])
        pred_scores_classes = keras_rcnn.backend.gather_nd(pred_scores, keras.backend.concatenate([keras.backend.expand_dims(indices), keras.backend.expand_dims(pred_classes)], axis=1))
        indices_boxes = keras.backend.concatenate([4 * pred_classes, 4 * pred_classes + 1, 4 * pred_classes + 2, 4 * pred_classes + 3], 0)
        indices = keras.backend.tile(indices, [4])
        pred_boxes = keras_rcnn.backend.gather_nd(pred_boxes, keras.backend.concatenate(keras.backend.expand_dims(indices), keras.backend.expand_dims(indices_boxes)))

        indices = keras_rcnn.backend.non_maximum_suppression(pred_boxes, pred_scores_classes, keras.backend.shape(pred_boxes)[1], self.TEST_NMS)
        pred_scores = keras.backend.gather(pred_scores, indices)
        pred_boxes = keras.backend.gather(pred_boxes, indices)


        return keras.backend.expand_dims(pred_boxes, 0), keras.backend.expand_dims(pred_scores, 0)

    def compute_output_shape(self, input_shape):
        return (1, None, 4), (1, None, 3)
