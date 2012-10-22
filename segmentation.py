from opencv_utils import show_image_and_wait_for_key, draw_segments, BlurProcessor
from processor import DisplayingProcessor, DisplayingProcessorStack, create_broadcast
from segmentation_aux import SegmentOrderer, guess_line_starts_ends_and_middles, guess_line_starts
from segmentation_filters import DEFAULT_FILTER_STACK, Filter, NearLineFilter
import numpy
import cv2

SEGMENT_DATATYPE=   numpy.uint16
SEGMENT_SIZE=       4
SEGMENTS_DIRECTION= 0 # vertical axis in numpy

def segments_from_numpy( segments ):
    '''reverses segments_to_numpy'''
    segments= segments if SEGMENTS_DIRECTION==0 else segments.tranpose()
    segments= [map(int,s) for s in segments]
    return segments

def segments_to_numpy( segments ):
    '''given a list of 4-element tuples, transforms it into a numpy array'''
    segments= numpy.array( segments, dtype=SEGMENT_DATATYPE, ndmin=2)   #each segment in a row
    segments= segments if SEGMENTS_DIRECTION==0 else numpy.transpose(segments)
    return segments

def best_segmenter(image):
    '''returns a segmenter instance which segments the given image well'''
    return ContourSegmenter()

def region_from_segment( image, segment ):
    '''given a segment (rectangle) and an image, returns it's corresponding subimage'''
    x,y,w,h= segment
    return image[y:y+h,x:x+w]


class RawSegmenter( DisplayingProcessor ):
    '''A image segmenter. input is image, output is segments'''    
    def _segment( self, image ):
        '''segments an opencv image for OCR. returns list of 4-element tuples (x,y,width, height).'''
        #return segments
        raise NotImplementedError()

    def display(self, display_before=False):
        image= self.image.copy()
        if display_before:
            show_image_and_wait_for_key(image, "image before segmentation")
        draw_segments( image, self.segments)
        show_image_and_wait_for_key(image, "image after segmentation by "+self.__class__.__name__)

    def _process( self, image):
        segments= self._segment(image)
        self.image, self.segments= image, segments
        return segments

class FullSegmenter( DisplayingProcessorStack ):
    pass

class RawContourSegmenter( RawSegmenter ):
    PARAMETERS=  RawSegmenter.PARAMETERS + {"block_size":11, "c":10 }
    def _segment( self, image ):
        self.image= image
        image= cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        image = cv2.adaptiveThreshold(image, maxValue=255, adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C, thresholdType=cv2.THRESH_BINARY, blockSize=self.block_size, C=self.c)
        contours,hierarchy = cv2.findContours(image,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
        segments= segments_to_numpy( [cv2.boundingRect(c) for c in contours] )
        self.contours, self.hierarchy= contours, hierarchy #store, may be needed for debugging
        return segments

class ContourSegmenter( FullSegmenter ):
    CLASSES= [BlurProcessor, RawContourSegmenter]+DEFAULT_FILTER_STACK+[SegmentOrderer]
    def __init__(self, **args):
        stack = [c() for c in ContourSegmenter.CLASSES]
        FullSegmenter.__init__(self, stack, **args)
        filters= [s for s in stack if isinstance(s, Filter)]
        i= map(lambda x:x.__class__, filters).index( NearLineFilter ) #position of NearLineFilter
        stack[0].add_prehook( create_broadcast( "_input", filters, "image" ) )
        filters[i-1].add_poshook( create_broadcast( "_output", filters[i], "lines", guess_line_starts_ends_and_middles) )
        filters[i-1].add_poshook( create_broadcast( "_output", stack[-1], "max_line_height", lambda x: numpy.max(numpy.diff(guess_line_starts(x))) ))
    
