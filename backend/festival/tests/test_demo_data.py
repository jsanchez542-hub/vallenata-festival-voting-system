from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from festival.models import Category, Edition, Option, Poll, PollStatus


class LoadDemoDataTests(TestCase):
    def load(self):
        call_command("load_demo_data", stdout=StringIO())

    def test_loads_the_prototype_sample_data(self):
        self.load()
        self.assertEqual(Edition.objects.get().number, 60)
        self.assertEqual(Category.objects.count(), 3)
        statuses = sorted(poll.status for poll in Poll.objects.all())
        expected = [PollStatus.CLOSED, PollStatus.OPEN, PollStatus.OPEN, PollStatus.UPCOMING]
        self.assertEqual(statuses, sorted(expected))
        self.assertEqual(Option.objects.count(), 14)

    def test_running_it_again_does_not_duplicate_rows(self):
        self.load()
        self.load()
        counts = [model.objects.count() for model in (Edition, Category, Poll, Option)]
        self.assertEqual(counts, [1, 3, 4, 14])
