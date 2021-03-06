"""Collection of tests for the reports module."""
import faker
from django.test import TestCase

from account import reports
from account.models import InstanceEvent
from account.tests import helper as account_helper
from util.tests import helper as util_helper

HOUR = 60. * 60
DAY = HOUR * 24
HOURS_5 = HOUR * 5
HOURS_10 = HOUR * 10
HOURS_15 = HOUR * 15
DAYS_31 = DAY * 31

_faker = faker.Faker()


class ReportTestBase(TestCase):
    """Base class for reporting tests that require some data setup."""

    def setUp(self):
        """
        Set up commonly used data for each test.

        From this rich combination of data, we should have enough data for some
        interesting tests! If you think your test needs more, consider adding
        to this based class setup.

        The rough hierarchy of initial objects looks something like this:

            user_1:
                image_plain
                image_rhel
                image_ocp
                image_rhel_ocp
                image_windows
                account_1:
                    instance_1
                    instance_2
                    instance_3
                    instance_4
                    instance_5
                account_2:
                    None

            user_2:
                account_3:
                    None
                account_4:
                    None

            user_super:
                None
        """
        self.user_1 = util_helper.generate_test_user()
        self.user_2 = util_helper.generate_test_user()
        self.user_super = util_helper.generate_test_user(is_superuser=True)

        self.account_1 = account_helper.generate_aws_account(
            user=self.user_1, name=_faker.bs())
        self.account_2 = account_helper.generate_aws_account(
            user=self.user_1, name=_faker.bs())
        self.account_3 = account_helper.generate_aws_account(
            user=self.user_2, name=_faker.bs())
        self.account_4 = account_helper.generate_aws_account(
            user=self.user_2, name=_faker.bs())

        self.instance_1 = account_helper.generate_aws_instance(self.account_1)
        self.instance_2 = account_helper.generate_aws_instance(self.account_1)
        self.instance_3 = account_helper.generate_aws_instance(self.account_1)
        self.instance_4 = account_helper.generate_aws_instance(self.account_1)
        self.instance_5 = account_helper.generate_aws_instance(self.account_1)

        self.image_plain = account_helper.generate_aws_image(self.account_1)
        self.image_windows = account_helper.generate_aws_image(
            self.account_1, is_windows=True)
        self.image_rhel = account_helper.generate_aws_image(
            self.account_1, is_rhel=True)
        self.image_ocp = account_helper.generate_aws_image(
            self.account_1, is_openshift=True)
        self.image_rhel_ocp = account_helper.generate_aws_image(
            self.account_1, is_rhel=True, is_openshift=True)

        # Report on "month of January in 2018"
        self.start = util_helper.utc_dt(2018, 1, 1, 0, 0, 0)
        self.end = util_helper.utc_dt(2018, 2, 1, 0, 0, 0)

    def generate_events(self, powered_times, instance=None, image=None):
        """
        Generate events saved to the DB and returned.

        Args:
            powered_times (list[tuple]): Time periods instance is powered on.
            instance (Instance): Optional which instance has the events. If
                not specified, default is self.instance_1.
            image (AwsMachineImage): Optional which image seen in the events.
                If not specified, default is self.image_rhel.

        Returns:
            list[InstanceEvent]: The list of events

        """
        if instance is None:
            instance = self.instance_1
        if image is None:
            image = self.image_rhel
        events = account_helper.generate_aws_instance_events(
            instance, powered_times, image.ec2_ami_id,
        )
        return events


class GetDailyUsageTestBase(ReportTestBase):
    """Base class for testing get_daily_usage with additional assertions."""

    def assertTotalRunningTimes(self, results, rhel=0, openshift=0):
        """Assert total expected running times for rhel and openshift."""
        self.assertEqual(sum((
            day['rhel_runtime_seconds'] for day in results['daily_usage']
        )), rhel)
        self.assertEqual(sum((
            day['openshift_runtime_seconds'] for day in results['daily_usage']
        )), openshift)

    def assertDaysSeen(self, results, rhel=0, openshift=0):
        """Assert expected days seen having rhel and openshift instances."""
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['rhel_instances'] > 0
        )), rhel)
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['openshift_instances'] > 0
        )), openshift)

    def assertInstancesSeen(self, results, rhel=0, openshift=0):
        """Assert total expected numbers of rhel and openshift instances."""
        self.assertEqual(results['instances_seen_with_rhel'], rhel)
        self.assertEqual(results['instances_seen_with_openshift'], openshift)

    def assertNoActivityFound(self, results):
        """Assert no relevant activity found in the report results."""
        self.assertTotalRunningTimes(results)
        self.assertDaysSeen(results)
        self.assertInstancesSeen(results)


class GetDailyUsageNoReportableActivity(GetDailyUsageTestBase):
    """get_daily_usage for cases that should produce no report output."""

    def test_no_events(self):
        """Assert empty report when no events exist."""
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertNoActivityFound(results)

    def test_events_only_in_past(self):
        """Assert empty report when events exist only in the past."""
        powered_times = (
            (
                util_helper.utc_dt(2017, 1, 9, 0, 0, 0),
                util_helper.utc_dt(2017, 1, 10, 0, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertNoActivityFound(results)

    def test_events_only_in_future(self):
        """Assert empty report when events exist only in the past."""
        powered_times = (
            (
                util_helper.utc_dt(2019, 1, 9, 0, 0, 0),
                util_helper.utc_dt(2019, 1, 10, 0, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertNoActivityFound(results)

    def test_events_in_other_user_account(self):
        """Assert empty report when events exist only for a different user."""
        powered_times = (
            (
                util_helper.utc_dt(2019, 1, 9, 0, 0, 0),
                util_helper.utc_dt(2019, 1, 10, 0, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_2.id, self.start, self.end)
        self.assertNoActivityFound(results)

    def test_events_not_rhel_not_openshift(self):
        """Assert empty report when events exist only for plain images."""
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 9, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0)
            ),
        )
        self.generate_events(powered_times, image=self.image_plain)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertNoActivityFound(results)


class GetDailyUsageBasicInstanceTest(GetDailyUsageTestBase):
    """get_daily_usage tests for an account with one relevant RHEL instance."""

    def test_usage_on_in_off_in(self):
        """
        Assert usage for 5 hours powered in the period.

        This test asserts counting when there's a both power-on event and a
        power-off event 5 hours apart inside the report window.

        The instance's running time in the window would look like:
            [        ##                     ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5)
        self.assertDaysSeen(results, rhel=1)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_in_on_in_off_in(self):
        """
        Assert usage for 5 hours powered in the period.

        This test asserts counting when there's a both power-on event, a second
        bogus power-on even 1 hour later, and a power-off event 4 more hours
        later, all inside the report window.

        The instance's running time in the window would look like:
            [        ##                     ]
        """
        powered_times = (
            (util_helper.utc_dt(2018, 1, 10, 0, 0, 0), None),
            (
                util_helper.utc_dt(2018, 1, 10, 1, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5)
        self.assertDaysSeen(results, rhel=1)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_before_off_in(self):
        """
        Assert usage for 5 hours powered in the period.

        This test asserts counting when there was a power-on event before the
        report window starts and a power-off event 5 hours into the window.

        The instance's running time in the window would look like:
            [##                             ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2017, 1, 1, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 1, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5)
        self.assertDaysSeen(results, rhel=1)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_in(self):
        """
        Assert usage for 5 hours powered in the period.

        This test asserts counting when there was only a power-on event 5 hours
        before the report window ends.

        The instance's running time in the window would look like:
            [                             ##]
        """
        powered_times = ((util_helper.utc_dt(2018, 1, 31, 19, 0, 0), None),)
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5)
        self.assertDaysSeen(results, rhel=1)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_over_multiple_days_then_off(self):
        """
        Assert usage when powered on over multiple days.

        This test asserts counting when there was a power-on event at the start
        of the reporting window start, several days pass, and then a power-off
        event before the window ends.

        The instance's running time in the window would look like:
            [######                         ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2017, 1, 1, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 6, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=DAY * 5 + HOURS_5)
        self.assertDaysSeen(results, rhel=6)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_before_off_never(self):
        """
        Assert usage for all 31 days powered in the period.

        This test asserts counting when there was a power-on event before
        the report window starts and nothing else.

        The instance's running time in the window would look like:
            [###############################]
        """
        powered_times = ((util_helper.utc_dt(2017, 1, 1), None),)
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=DAYS_31)
        self.assertDaysSeen(results, rhel=31)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_before_off_after(self):
        """
        Assert usage for all 31 days powered in the period.

        This test asserts counting when there was a power-on event before
        the report window starts and a power-off event after the window ends.

        The instance's running time in the window would look like:
            [###############################]
        """
        powered_times = (
            (util_helper.utc_dt(2017, 1, 1), util_helper.utc_dt(2019, 1, 1)),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=DAYS_31)
        self.assertDaysSeen(results, rhel=31)
        self.assertInstancesSeen(results, rhel=1)

    def test_usage_on_before_off_in_on_in_off_in_on_in(self):
        """
        Assert usage for 15 hours powered in the period.

        This test asserts counting when there was a power-on event before the
        reporting window start, a power-off event 5 hours into the window, a
        power-on event in the middle of the window, a power-off event 5 hours
        later, and a power-on event 5 hours before the window ends

        The instance's running time in the window would look like:
            [##            ##             ##]
        """
        powered_times = (
            (
                util_helper.utc_dt(2017, 1, 1, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 1, 5, 0, 0)
            ),
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
            (util_helper.utc_dt(2018, 1, 31, 19, 0, 0), None),
        )
        self.generate_events(powered_times)
        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_15)
        self.assertDaysSeen(results, rhel=3)
        self.assertInstancesSeen(results, rhel=1)


class GetDailyUsageTwoRhelInstancesTest(GetDailyUsageTestBase):
    """
    get_daily_usage tests for 1 account with 2 RHEL instances.

    This simulates the case of one customer having two instances running the
    same RHEL image at different times.
    """

    def test_usage_on_times_not_overlapping(self):
        """
        Assert usage for 10 hours powered in the period.

        This test asserts counting when one instance was on for 5 hours
        and another instance was on for 5 hours at a different time.

        The instances' running times in the window would look like:
            [        ##                     ]
            [                    ##         ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times)

        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 20, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 20, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times, instance=self.instance_2)

        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_10)
        self.assertDaysSeen(results, rhel=2)
        self.assertInstancesSeen(results, rhel=2)

    def test_usage_on_times_overlapping(self):
        """
        Assert usage for 10 hours powered in the period.

        This test asserts counting when one instance was on for 5 hours and
        another instance was on for 5 hours at a another time that overlaps
        with the first by 2.5 hours.

        The instances' running times in the window would look like:
            [        ##                     ]
            [         ##                    ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_1)

        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 2, 30, 0),
                util_helper.utc_dt(2018, 1, 10, 7, 30, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_2)

        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_10)
        self.assertDaysSeen(results, rhel=1)
        self.assertInstancesSeen(results, rhel=2)


class GetDailyUsageOneRhelOneOpenShiftInstanceTest(GetDailyUsageTestBase):
    """
    get_daily_usage tests for 1 account with 1 RHEL and 1 OpenShift instance.

    This simulates the case of one customer having one instance using a RHEL
    image and one instance using an OpenShift image running at different times.
    """

    def test_usage_on_times_not_overlapping(self):
        """
        Assert usage for 5 hours RHEL and 5 hours OpenShift in the period.

        This test asserts counting when the RHEL instance was on for 5 hours
        and the OpenShift instance was on for 5 hours at a different time.

        The instances' running times in the window would look like:
            [        ##                     ]
            [                    ##         ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_1, self.image_rhel)

        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 20, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 20, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_2, self.image_ocp)

        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5, openshift=HOURS_5)
        self.assertDaysSeen(results, rhel=1, openshift=1)
        self.assertInstancesSeen(results, rhel=1, openshift=1)

    def test_usage_on_times_overlapping(self):
        """
        Assert overlapping RHEL and OpenShift times are reported separately.

        This test asserts counting when the RHEL instance was on for 5 hours
        and the OpenShift instance was on for 5 hours at a another time that
        overlaps with the first by 2.5 hours.

        The instances' running times in the window would look like:
            [        ##                     ]
            [         ##                    ]
        """
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_1, self.image_rhel)

        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 2, 30, 0),
                util_helper.utc_dt(2018, 1, 10, 7, 30, 0)
            ),
        )
        self.generate_events(powered_times, self.instance_2, self.image_ocp)

        results = reports.get_daily_usage(self.user_1.id, self.start, self.end)
        self.assertTotalRunningTimes(results, rhel=HOURS_5, openshift=HOURS_5)
        self.assertDaysSeen(results, rhel=1, openshift=1)
        self.assertInstancesSeen(results, rhel=1, openshift=1)


class GetDailyUsageComplexInstancesTest(GetDailyUsageTestBase):
    """get_time_usage tests for 1 account and several instances."""

    def test_several_instances_with_whole_days(self):
        """
        Assert correct report for instances with various run times.

        The RHEL-only running times over the month would look like:

            [ ####      ##                  ]
            [  ##                ##         ]

        The plain running times over the month would look like:

            [  #####                        ]

        The OpenShift-only running times over the month would look like:

            [                  ###          ]

        The RHEL+OpenShift running times over the month would look like:

            [        #          ##          ]
        """
        powered_times_1 = (
            (
                util_helper.utc_dt(2018, 1, 2, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 6, 0, 0, 0)
            ),
            (
                util_helper.utc_dt(2018, 1, 12, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 14, 0, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_1,
            powered_times_1,
            ec2_ami_id=self.image_rhel.ec2_ami_id,
        )

        powered_times_2 = (
            (
                util_helper.utc_dt(2018, 1, 3, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 5, 0, 0, 0)
            ),
            (
                util_helper.utc_dt(2018, 1, 21, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 23, 0, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_2,
            powered_times_2,
            ec2_ami_id=self.image_rhel.ec2_ami_id,
        )

        powered_times_3 = (
            (
                util_helper.utc_dt(2018, 1, 3, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 8, 0, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_3,
            powered_times_3,
            ec2_ami_id=self.image_plain.ec2_ami_id,
        )

        powered_times_4 = (
            (
                util_helper.utc_dt(2018, 1, 19, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 22, 0, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_4,
            powered_times_4,
            ec2_ami_id=self.image_ocp.ec2_ami_id,
        )

        powered_times_5 = (
            (
                util_helper.utc_dt(2018, 1, 9, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0)
            ),
            (
                util_helper.utc_dt(2018, 1, 20, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 22, 0, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_5,
            powered_times_5,
            ec2_ami_id=self.image_rhel_ocp.ec2_ami_id,
        )

        results = reports.get_daily_usage(
            self.account_1.user_id,
            self.start,
            self.end,
        )

        self.assertEqual(len(results['daily_usage']), 31)
        self.assertInstancesSeen(results, rhel=3, openshift=2)

        # total of rhel seconds should be 13 days worth of seconds.
        # total of openshift seconds should be 6 days worth of seconds.
        self.assertTotalRunningTimes(results, rhel=DAY * 13, openshift=DAY * 6)

        # number of individual days in which we saw anything rhel is 10
        # number of individual days in which we saw anything openshift is 4
        self.assertDaysSeen(results, rhel=10, openshift=4)

        # number of days in which we saw 2 rhel running all day is 3
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['rhel_runtime_seconds'] == DAY * 2
        )), 3)

        # number of days in which we saw 1 rhel running all day is 7
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['rhel_runtime_seconds'] == DAY
        )), 7)

        # number of days in which we saw 1 openshift running all day is 2
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['openshift_runtime_seconds'] == DAY * 2
        )), 2)

        # number of days in which we saw 2 openshift running all day is 2
        self.assertEqual(sum((
            1 for day in results['daily_usage']
            if day['openshift_runtime_seconds'] == DAY * 2
        )), 2)


class GetCloudAccountOverview(TestCase):
    """Test that the CloudAccountOverview functions act correctly."""

    def setUp(self):
        """Set up commonly used data for each test."""
        # set up start & end dates and images
        self.start = util_helper.utc_dt(2018, 1, 1, 0, 0, 0)
        self.end = util_helper.utc_dt(2018, 2, 1, 0, 0, 0)
        self.account = account_helper.generate_aws_account()
        self.account.created_at = util_helper.utc_dt(2017, 1, 1, 0, 0, 0)
        self.account.save()
        # set up an account created after the end date for testing
        self.account_after_end = account_helper.generate_aws_account()
        self.account_after_end.created_at = \
            util_helper.utc_dt(2018, 3, 1, 0, 0, 0)
        self.account_after_end.save()
        # set up an account created on the end date for testing
        self.account_on_end = account_helper.generate_aws_account()
        self.account_on_end.created_at = self.end
        self.account_on_end.save()
        self.windows_image = account_helper.generate_aws_image(
            self.account,
            is_encrypted=False,
            is_windows=True,
        )
        self.rhel_image = account_helper.generate_aws_image(
            self.account,
            is_encrypted=False,
            is_windows=False,
            ec2_ami_id=None,
            is_rhel=True,
            is_openshift=False)
        self.openshift_image = account_helper.generate_aws_image(
            self.account,
            is_encrypted=False,
            is_windows=False,
            ec2_ami_id=None,
            is_rhel=False,
            is_openshift=True)
        self.openshift_and_rhel_image = account_helper.generate_aws_image(
            self.account,
            is_encrypted=False,
            is_windows=False,
            ec2_ami_id=None,
            is_rhel=True,
            is_openshift=True)
        self.instance_1 = account_helper.generate_aws_instance(self.account)
        self.instance_2 = account_helper.generate_aws_instance(self.account)

    def assertExpectedAccountOverview(self, overview, account,
                                      images=0, instances=0,
                                      rhel_instances=0, openshift_instances=0):
        """Assert results match the expected account info and counters."""
        expected_overview = {
            'id': account.id,
            'cloud_account_id': account.aws_account_id,
            'user_id': account.user_id,
            'type': account.cloud_type,
            'arn': account.account_arn,
            'creation_date': account.created_at,
            'name': account.name,
            'images': images,
            'instances': instances,
            'rhel_instances': rhel_instances,
            'openshift_instances': openshift_instances,
        }
        self.assertEqual(expected_overview, overview)

    def test_get_cloud_account_overview_no_events(self):
        """Assert an overview of an account with no events returns 0s."""
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        self.assertExpectedAccountOverview(overview, self.account)

    def test_get_cloud_account_overview_with_events(self):
        """Assert an account overview reports instances/images correctly."""
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_1, powered_times,
            self.windows_image.ec2_ami_id
        )
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=1, instances=1)

    def test_get_cloud_account_overview_with_rhel_image(self):
        """Assert an account overview with events reports rhel correctly."""
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_1, powered_times,
            self.windows_image.ec2_ami_id
        )
        # in addition to instance_1's events, we are creating an event for
        # instance_2 with a rhel_image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.rhel_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # we expect to find 2 total images, 2 total instances and 1 rhel
        # instance
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=2, instances=2,
                                           rhel_instances=1)

    def test_get_cloud_account_overview_with_openshift_image(self):
        """Assert an account overview with events reports correctly."""
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_1, powered_times,
            self.windows_image.ec2_ami_id
        )
        # in addition to instance_1's events, we are creating an event for
        # instance_2 with an openshift_image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # we expect to find 2 total images, 2 total instances and 1
        # openshift instance
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=2, instances=2,
                                           openshift_instances=1)

    def test_get_cloud_account_overview_with_openshift_and_rhel_image(self):
        """Assert an account overview reports openshift and rhel correctly."""
        powered_times = (
            (
                util_helper.utc_dt(2018, 1, 10, 0, 0, 0),
                util_helper.utc_dt(2018, 1, 10, 5, 0, 0)
            ),
        )
        account_helper.generate_aws_instance_events(
            self.instance_1, powered_times,
            self.windows_image.ec2_ami_id
        )
        # in addition to instance_1's events, we are creating an event for
        # instance_2 with a rhel & openshift_image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_and_rhel_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # we expect to find 2 total images, 2 total instances, 1 rhel instance
        # and 1 openshift instance
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=2, instances=2,
                                           rhel_instances=1,
                                           openshift_instances=1)

    def test_get_cloud_account_overview_with_two_instances_same_image(self):
        """Assert an account overview reports images correctly."""
        # generate event for instance_1 with the rhel/openshift image
        account_helper.generate_single_aws_instance_event(
            self.instance_1, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_and_rhel_image.ec2_ami_id)
        # generate event for instance_2 with the rhel/openshift image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_and_rhel_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # assert that we only find the one image
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=1, instances=2,
                                           rhel_instances=1,
                                           openshift_instances=1)

    def test_get_cloud_account_overview_with_rhel(self):
        """Assert an account overview reports rhel correctly."""
        # generate event for instance_1 with the rhel/openshift image
        account_helper.generate_single_aws_instance_event(
            self.instance_1, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_and_rhel_image.ec2_ami_id)
        # generate event for instance_2 with the rhel image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.rhel_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # assert that we only find the two rhel images
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=2, instances=2,
                                           rhel_instances=2,
                                           openshift_instances=1)

    def test_get_cloud_account_overview_with_openshift(self):
        """Assert an account overview reports openshift correctly."""
        # generate event for instance_1 with the rhel/openshift image
        account_helper.generate_single_aws_instance_event(
            self.instance_1, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_and_rhel_image.ec2_ami_id)
        # generate event for instance_2 with the openshift image
        account_helper.generate_single_aws_instance_event(
            self.instance_2, self.start, InstanceEvent.TYPE.power_on,
            self.openshift_image.ec2_ami_id)
        overview = reports.get_account_overview(
            self.account, self.start, self.end)
        # assert that we only find the two openshift images
        self.assertExpectedAccountOverview(overview, self.account,
                                           images=2, instances=2,
                                           rhel_instances=1,
                                           openshift_instances=2)

    def test_get_cloud_account_overview_account_creation_after(self):
        """Assert an overview of an account created after end reports None."""
        overview = reports.get_account_overview(
            self.account_after_end, self.start, self.end)
        self.assertExpectedAccountOverview(overview, self.account_after_end,
                                           images=None, instances=None,
                                           rhel_instances=None,
                                           openshift_instances=None)

    def test_get_cloud_account_overview_account_creation_on(self):
        """Assert an overview of an account created on end reports None."""
        overview = reports.get_account_overview(
            self.account_on_end, self.start, self.end)
        self.assertExpectedAccountOverview(overview, self.account_on_end,
                                           images=None, instances=None,
                                           rhel_instances=None,
                                           openshift_instances=None)

    # the following tests are assuming that the events have been returned
    # from the _get_relevant_events() function which will only return events
    # during the specified time period **or** if no events exist during the
    # time period, the last event that occurred. Therefore, the validate method
    # makes sure that we ignore out the off events that occurred before start
    def test_validate_event_off_after_start(self):
        """Test that an off event after start is a valid event to inspect."""
        powered_time = util_helper.utc_dt(2018, 1, 10, 0, 0, 0)

        event = account_helper.generate_single_aws_instance_event(
            self.instance_1, powered_time, InstanceEvent.TYPE.power_off
        )
        is_valid = reports.validate_event(event, self.start)
        self.assertEqual(is_valid, True)

    def test_validate_event_on_after_start(self):
        """Test that an on event after start is a valid event to inspect."""
        powered_time = util_helper.utc_dt(2018, 1, 10, 0, 0, 0)

        event = account_helper.generate_single_aws_instance_event(
            self.instance_1, powered_time, InstanceEvent.TYPE.power_on
        )
        is_valid = reports.validate_event(event, self.start)
        self.assertEqual(is_valid, True)

    def test_validate_event_on_before_start(self):
        """Test that an on event before start is a valid event to inspect."""
        powered_time = util_helper.utc_dt(2017, 12, 10, 0, 0, 0)

        event = account_helper.generate_single_aws_instance_event(
            self.instance_1, powered_time, InstanceEvent.TYPE.power_on
        )
        is_valid = reports.validate_event(event, self.start)
        self.assertEqual(is_valid, True)

    def test_validate_event_off_before_start(self):
        """Test that an off event before start is not a valid event."""
        powered_time = util_helper.utc_dt(2017, 12, 10, 0, 0, 0)

        event = account_helper.generate_single_aws_instance_event(
            self.instance_1, powered_time, InstanceEvent.TYPE.power_off
        )
        is_valid = reports.validate_event(event, self.start)
        self.assertEqual(is_valid, False)
