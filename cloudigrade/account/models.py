"""Cloudigrade Account Models."""
from abc import abstractmethod

import model_utils
from django.contrib.auth.models import User
from django.db import models

from account import AWS_PROVIDER_STRING
from util.models import (BaseModel,
                         BasePolymorphicModel)


class Account(BasePolymorphicModel):
    """Base customer account model."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
    )
    name = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        db_index=True
    )

    @property
    @abstractmethod
    def cloud_account_id(self):
        """Get the external cloud provider's ID for this account."""

    @property
    @abstractmethod
    def cloud_type(self):
        """Get the external cloud provider type."""


class ImageTag(BaseModel):
    """Tag types for images."""

    description = models.CharField(
        max_length=32,
        null=False,
        blank=False
    )


class MachineImage(BasePolymorphicModel):
    """Base model for a cloud VM image."""

    PENDING = 'pending'
    PREPARING = 'preparing'
    INSPECTING = 'inspecting'
    INSPECTED = 'inspected'
    STATUS_CHOICES = (
        (PENDING, 'Pending Inspection'),
        (PREPARING, 'Preparing for Inspection'),
        (INSPECTING, 'Being Inspected'),
        (INSPECTED, 'Inspected'),
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
    )
    tags = models.ManyToManyField(ImageTag, blank=True)
    inspection_json = models.TextField(null=True,
                                       blank=True)
    is_encrypted = models.NullBooleanField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default=PENDING)

    @property
    def rhel(self):
        """
        Indicate if the image is tagged for RHEL.

        Returns:
            bool: True if a 'rhel' tag exists for this image, else False.

        """
        return self.tags.filter(description='rhel').exists()

    @property
    def openshift(self):
        """
        Indicate if the image is tagged for OpenShift.

        Returns:
            bool: True if an 'openshift' tag exists for this image, else False.

        """
        return self.tags.filter(description='openshift').exists()


class Instance(BasePolymorphicModel):
    """Base model for a compute/VM instance in a cloud."""

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
    )


class InstanceEvent(BasePolymorphicModel):
    """Base model for an event triggered by a Instance."""

    TYPE = model_utils.Choices(
        'power_on',
        'power_off',
    )
    instance = models.ForeignKey(
        Instance,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
    )
    machineimage = models.ForeignKey(
        MachineImage,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
    )
    event_type = models.CharField(
        max_length=32,
        choices=TYPE,
        null=False,
        blank=False,
    )
    occurred_at = models.DateTimeField(null=False)


class AwsAccount(Account):
    """Amazon Web Services customer account model."""

    aws_account_id = models.CharField(max_length=16, db_index=True)
    account_arn = models.CharField(max_length=256, unique=True)

    @property
    def cloud_account_id(self):
        """Get the AWS Account ID for this account."""
        return self.aws_account_id

    @property
    def cloud_type(self):
        """Get the cloud type to indicate this account uses AWS."""
        return AWS_PROVIDER_STRING


class AwsInstance(Instance):
    """Amazon Web Services EC2 instance model."""

    ec2_instance_id = models.CharField(
        max_length=256,
        unique=True,
        db_index=True,
        null=False,
        blank=False,
    )
    region = models.CharField(
        max_length=256,
        null=False,
        blank=False,
    )


class AwsMachineImage(MachineImage):
    """MachineImage model for an AWS EC2 instance."""

    ec2_ami_id = models.CharField(
        max_length=256,
        unique=True,
        db_index=True,
        null=False,
        blank=False
    )


class AwsMachineImageCopy(AwsMachineImage):
    """
    Special machine image model for when we needed to make a copy.

    There are some cases in which we have to create and leave in the customer's
    AWS account a copy of an AWS image, but we need to keep track of this and
    somehow notify the customer about its existence.

    This model class extends all the same attributes of AwsMachineImage but
    adds a foreign key to point to the original reference image from which this
    copy was made.
    """

    reference_awsmachineimage = models.ForeignKey(
        AwsMachineImage,
        on_delete=models.CASCADE,
        db_index=True,
        null=False,
        related_name='+'
    )


class AwsInstanceEvent(InstanceEvent):
    """Event model for an event triggered by an AwsInstance."""

    subnet = models.CharField(max_length=256, null=False, blank=False)
    instance_type = models.CharField(max_length=64, null=False, blank=False)
