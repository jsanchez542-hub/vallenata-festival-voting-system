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
        expected = [PollStatus.CLOSED, *[PollStatus.OPEN] * 3, PollStatus.UPCOMING]
        self.assertEqual(statuses, sorted(expected))
        self.assertEqual(Option.objects.count(), 17)

    def test_two_open_polls_share_a_category(self):
        self.load()
        music = Category.objects.get(name="Música")
        self.assertEqual(music.polls.open().count(), 2)

    def test_running_it_again_does_not_duplicate_rows(self):
        self.load()
        self.load()
        counts = [model.objects.count() for model in (Edition, Category, Poll, Option)]
        self.assertEqual(counts, [1, 3, 5, 17])
