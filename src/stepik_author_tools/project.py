"""Compatibility imports; project loading lives in the course package."""

from .course.project import Course as Course
from .course.project import load_course as load_course
from .serialization.jsonio import contained as contained
from .serialization.jsonio import read as read
