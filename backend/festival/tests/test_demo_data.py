from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import F, Q
from django.test import TestCase

from festival.models import Category, Edition, Option, Poll, PollStatus, Vote


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

    def test_three_polls_get_sample_votes(self):
        self.load()
        totals = {poll.slug: poll.tally().total for poll in Poll.objects.all()}
        self.assertEqual(
            totals,
            {
                "cancion-favorita-del-publico": 34,
                "agrupacion-favorita-del-publico": 56,
                "vestuario-mas-destacado": 0,
                "comparsa-favorita-del-desfile": 0,
                "presentacion-mas-recordada": 74,
            },
        )

    def test_sample_votes_fall_inside_each_poll_window(self):
        self.load()
        outside = Q(cast_at__lt=F("option__poll__opens_at")) | Q(
            cast_at__gt=F("option__poll__closes_at")
        )
        self.assertFalse(Vote.objects.filter(outside).exists())

    def test_nobody_can_sign_in_with_the_sample_voters(self):
        self.load()
        voters = get_user_model().objects.all()
        self.assertEqual(voters.count(), 90)
        self.assertFalse(any(voter.has_usable_password() for voter in voters))

    def test_running_it_again_does_not_duplicate_rows(self):
        self.load()
        self.load()
        models = (Edition, Category, Poll, Option, Vote, get_user_model())
        self.assertEqual([model.objects.count() for model in models], [1, 3, 5, 17, 164, 90])
