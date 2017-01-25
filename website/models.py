"""
This file defines special model classes that are used to create and manipulate
SQL tables.

Create an SQL database with these model definitions by running:

python3 manage.py makemigrations website
python3 manage.py migrate
"""

from django.db import models
from django.utils import timezone
from .constants import *

import docker
import os
import subprocess
import time

WEBSITE_DEVELOP = True

# unimplemented tasks: 3, 20
TASK_TRAINING = [21, 22]
TASK_BLOCK_I = [5, 10, 6, 9, 19, 1, 18, 17, 16]
TASK_BLOCK_II = [8, 7, 2, 14, 12, 4, 13, 15, 11]

treatment_names = {
    'A': 'Tellina or Google Search',
    'B': 'Google Search'
}

# key: treatment order + study session stage
# value: treatment
treatment_assignments = {
    '0I': 'A',
    '0II': 'B',
    '1I': 'B',
    '1II': 'A'
}

class User(models.Model):
    """
    Describes a study participant.

    :member access_code: Code which uniquely identifies a study participant.
        Participants will use this to log into the task interface.
    :member first_name: user's first name
    :member last_name: user's last name
    :member group: user's group assignment
        Group 1: task block 1 + Tellina / task block 2 + Google
        Group 2: task block 1 + Google / task block 2 + Tellina
        Group 3: task block 2 + Tellina / task block 1 + Google
        Group 4: task block 2 + Google / task block 1 + Tellina
    """
    access_code = models.TextField()
    first_name = models.TextField()
    last_name = models.TextField()
    group = models.TextField(default='group1')


class Task(models.Model):
    """
    Describes a task used in the study.

    :member task_id: The ID that uniquely identifies a task. This makes the
        implementation of task scheduler easier.
    :member type: The type of task. Can be 'stdout', 'file_search' or
        'filesystem_change'.
    :member description: A precise description of the task.
    :member file_attributes: File attributes used in the tasks.
    :member initial_filesystem: JSON representation of the user's starting home
        directory
    :member goal_filesystem: JSON representation of the goal directory (if type
        is 'filesystem_change')
    :member stdout: The expected standard output for the task. Empty if task
        type is not 'stdout'.
    :member duration: How much time is alotted for the task.
    """
    task_id = models.PositiveIntegerField()
    type = models.TextField()
    description = models.TextField()
    file_attributes = models.TextField()
    initial_filesystem = models.TextField(default='')
    goal_filesystem = models.TextField(default='')
    stdout = models.TextField(default='')
    duration = models.DurationField()

# --- Container Management --- #

class Container(models.Model):
    """
    Describes information about a running Docker container.

    :member container_id: The ID of the container assigned by Docker.
    :member filesystem_name: The virtual filesystem that backs this container's
        home directory is located at /{filesystem_name}/home, which normally
        equals to the id of the study session the container is associated with.
    :member port: The host port through which the server in the container can
        be accessed.
    """
    container_id = models.TextField()
    filesystem_name = models.TextField()
    port = models.IntegerField()

    def destroy(self):
        """Destroys container, filesystem, and database entry."""

        # Destroy Docker container
        subprocess.run(['docker', 'rm', '-f', self.container_id])
        # Destroy filesystem
        subprocess.run(['/bin/bash', 'delete_filesystem.bash',
                        self.filesystem_name])
        # Delete table entry
        # self.delete()

def create_container(filesystem_name, task):
    """
    Creates a container whose filesystem is located at /{filesystem_name}/home
    on the host. The contents of filesystem are written to
    /{filesystem_name}/home.
    """

    # Make virtual filesystem
    subprocess.run(['/bin/bash', 'make_filesystem.bash', filesystem_name, HOME])

    # Create Docker container
    # NOTE: the created container does not run yet
    client = docker.Client(base_url='unix://var/run/docker.sock')
    docker_container = client.create_container(
        image='backend_container',
        ports=[10411],
        volumes=['/home/' + USER_NAME],
        host_config=client.create_host_config(
            binds={
                '/{}/home'.format(filesystem_name): {
                    'bind': '/home/' + USER_NAME,
                    'mode': 'rw',
                },
            },
            port_bindings={10411: ('0.0.0.0',)},
        ),
    )

    # Get ID of created container
    container_id = docker_container['Id']

    # Start container and write standard output and error to a log file
    subprocess.run(
        args='docker start -a {} >container_{}.log 2>&1 &'
            .format(container_id, container_id),
        shell=True,
        executable='/bin/bash',
    )

    # Wait a bit for container's to start
    time.sleep(1)

    # Set the permissions of the user's home directory.
    #
    # I tried to do this with the docker-py API and I couldn't get it to work,
    # so I'm just running a shell command.
    subprocess.call(['docker', 'exec', '-u', 'root', container_id,
        'chown', '-R', '{}:{}'.format(USER_NAME, USER_NAME),
        '/home/{}'.format(USER_NAME)])

    # Change file parameters according to the task specification if necessary
    if task.task_id == 3:
        # TODO: to read the owner of a file correctly, the disk_2_dict function
        # needs to read from the docker container instead of the virtual file
        # system
        subprocess.call(['docker', 'exec', '-u', 'root', container_id,
                         'adduser', USER_NAME, 'sudo'])
        # subprocess.call(['docker', 'exec', '-u', 'root', container_id, 'bash',
        # '-c', '\'echo "me ALL = (ALL) NOPASSWD: ALL" > /etc/sudoers\''])
        subprocess.call(['docker', 'exec', '-u', 'root', container_id,
                         'useradd', '-m', USER2_NAME])
    elif task.task_id == 7:
        filesystem_vfs_path = '/{}/home/website/'.format(filesystem_name)
        os.utime(filesystem_vfs_path + 'css/bootstrap3/bootstrap-glyphicons.css',
                 (1454065722, 1454065722))
        os.utime(filesystem_vfs_path + 'css/fonts/glyphiconshalflings-regular.eot',
                 (1454065722, 1454065722))
        os.utime(filesystem_vfs_path + 'css/fonts/glyphiconshalflings-regular.otf',
                 (1454065722, 1454065722))
        os.utime(filesystem_vfs_path + 'css/fonts/glyphiconshalflings-regular.svg',
                 (1454065722, 1454065722))
        os.utime(filesystem_vfs_path + 'css/fonts/glyphiconshalflings-regular.ttf',
                 (1454065722, 1454065722))
    elif task.task_id == 8:
        filesystem_vfs_path = '/{}/home/website/'.format(filesystem_name)
        os.utime(filesystem_vfs_path + 'content/labs/2013/10.md',
                 (1454065722, 1454065722))
        os.utime(filesystem_vfs_path + 'content/labs/2013/12.md',
                 (1454065722, 1454065722))

    # Find what port the container was mapped to
    info = client.inspect_container(container_id)
    port = int(info['NetworkSettings']['Ports']['10411/tcp'][0]['HostPort'])

    # Create container model object
    container = Container.objects.create(
        container_id=container_id,
        filesystem_name=filesystem_name,
        port=port,
    )

    return container


class StudySession(models.Model):
    """
    A study session participated by a user.

    :member user: The participant of the session.
    :member session_id: an application-wide unique study session ID.
    :member creation_time: Time the study session is created.
    :member close_time: Time the study session is closed.
    :member total_num_training_tasks: Total number of training tasks in the
        study session.
    :member total_num_tasks: Total number of tasks in the study session.

    :member current_task_session_id: The id of the task session that the user
        is undertaking. '' if no task session is running.
    :member num_tasks_completed: The number of tasks that has been completed in
        the study session.
    :member filesystem_change_seen: Set to true if a user has seen a file
        system change task in the study session.
    :member file_search_seen: Set to true if a user has seen a file search task
        in the study session.
    :member standard_output_seen: Set to true if a user has seen a standard
        output task in the study session.
    :member status: The state of the study session.
        - 'finished': The user has completed the study session.
        - 'closed_with_error': The session is closed due to exceptions.
        - 'paused': The user left the study session in the middle. Paused
            study sessions can be resumed.
        - 'pre-consent': The user has not signed the consent form.
        - 'pre-training': The user is at the pre-training stage of the study
            session.
        - 'training': The user is at the training stage of the study session.
        - 'running': The user is taking the study session.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.TextField(primary_key=True)
    creation_time = models.DateTimeField()
    end_time = models.DateTimeField(default='1111-11-11 00:00:00')
    total_num_training_tasks = models.PositiveIntegerField(
        default=len(TASK_TRAINING))
    total_num_tasks = models.PositiveIntegerField(
        default=len(TASK_BLOCK_I) + len(TASK_BLOCK_II))

    current_task_session_id = models.TextField(default='')
    num_tasks_completed = models.PositiveIntegerField(default=0)
    filesystem_change_seen = models.BooleanField(default=False)
    file_search_seen = models.BooleanField(default=False)
    standard_output_seen = models.BooleanField(default=False)
    status = models.TextField()

    def close(self, reason_for_close):
        # ignore already closed study sessions
        if self.status == 'running' or self.status == 'paused':
            self.current_task_session_id = ''
            self.close_time = timezone.now()
            self.status = reason_for_close
            self.save()

    def inc_num_tasks_completed(self):
        self.num_tasks_completed += 1
        if self.status == 'training' and \
            self.num_tasks_completed == self.total_num_training_tasks:
            # reset num_tasks_completed when the training session is completed
            self.num_tasks_completed = 0
            self.status = 'running'
        self.save()

    def stage_change(self):
        # check if the study session is going through a stage change
        if self.status == 'running':
            if self.num_tasks_completed == 0 or \
              self.num_tasks_completed == self.switch_point or \
              self.num_tasks_completed == self.total_num_tasks:
                return True
        return False

    def update_current_task_session_id(self):
        if self.status in ['pre-consent', 'pre-training', 'training']:
            new_task_session_id = self.session_id + \
                '-training-task-{}'.format(self.num_tasks_completed + 1)
        elif self.status == 'running':
            new_task_session_id = self.session_id + \
                '-task-{}'.format(self.num_tasks_completed + 1)
        else:
            raise ValueError('Wrong study session status: {} while updating '
                             'current task session id'.format(self.status))
        self.current_task_session_id = new_task_session_id
        self.save()
        return new_task_session_id

    def update_filesystem_change_seen(self):
        self.filesystem_change_seen = True
        self.save()

    def update_file_search_seen(self):
        self.file_search_seen = True
        self.save()

    def update_standard_output_seen(self):
        self.standard_output_seen = True
        self.save()

    @property
    def stage(self):
        # compute which stage of the study the user is currently at
        if not WEBSITE_DEVELOP:
            assert(len(TASK_BLOCK_I) == len(TASK_BLOCK_II))
        assert(self.num_tasks_completed <= self.total_num_tasks)

        if self.status in ['pre-consent', 'pre-training', 'training']:
            return 'O'
        elif self.status == 'running':
            if self.num_tasks_completed < self.switch_point:
                return 'I'
            elif self.num_tasks_completed < self.total_num_tasks:
                return 'II'
            else:
                return 'III'
        else:
            raise ValueError('Wrong study session status: {} while checking '
                             'current study session stage'.format(self.status))

    @property
    def task_block_order(self):
        # the task block order of the study session
        if self.user.group in ['group1', 'group4']:
            return '0'
        else:
            return '1'

    @property
    def switch_point(self):
        # number of tasks in the first part of the study
        if self.user.group in ['group1', 'group4']:
            return len(TASK_BLOCK_I)
        else:
            return len(TASK_BLOCK_II)

    @property
    def treatment_order(self):
        # the treatment order of the study session
        if self.user.group in ['group1', 'group3']:
            return '0'
        else:
            return '1'

class TaskSession(models.Model):
    """
    A task performed by a user in a study session.

    :member study_session: The study session to which the task session belong.
    :member study_session_stage: The part of the study session the task session
        is in.
    :member session_id: an application-wide unique task session ID.
    :member container: The Container model associated with the task session.
        None if no container is associated.
    :member is_training: Set to true if the task session is for training
        purpose.
    :member task: The task being performed in the task session.
    :member start_time: The start time of a task session.
    :member end_time: The end time of a task session. None if the task session
        is being undertaken.
    :member status: The state of the task result.
        - 'running':     The user has started the task, but the task has not
                         passed nor timed out yet
        - 'time_out':   The user started the task and did not pass it before
                         running out of time
        - 'quit':        The user quit the task
        - 'passed':      The user started the task and passed it
    """
    study_session = models.ForeignKey(StudySession, on_delete=models.CASCADE)
    study_session_stage = models.TextField()
    session_id = models.TextField(primary_key=True)
    container = models.ForeignKey(Container, default=None)
    is_training = models.BooleanField(default=False)
    task = models.ForeignKey(Task)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(default='1111-11-11 00:00:00')
    status = models.TextField()

    def close(self, reason_for_close):
        if self.task.type == 'stdout' and \
          not self.study_session.standard_output_seen:
            self.study_session.update_standard_output_seen()
        if self.task.type == 'file_search' and \
          not self.study_session.file_search_seen:
            self.study_session.update_file_search_seen()
        if self.task.type == 'filesystem_change' and \
          not self.study_session.filesystem_change_seen:
            self.study_session.update_filesystem_change_seen()
        self.end_time = timezone.now()
        self.container.destroy()
        self.status = reason_for_close
        self.save()

    def create_new_container(self):
        if self.container:
            # make sure any existing container is destroyed
            self.destroy_container()
        self.container = create_container(self.session_id, self.task)
        self.save()

    def destroy_container(self):
        self.container.destroy()
        self.container = None

    @property
    def page_tour(self):
        # check if page tour needs to be displayed for a task session
        page_tour = None
        if self.task.type == 'stdout':
            if not self.study_session.standard_output_seen:
                if self.study_session.status == 'training' and \
                                self.study_session.num_tasks_completed == 0:
                    page_tour = 'init_standard_output'
                else:
                    page_tour = 'first_standard_output'
        if self.task.type == 'file_search':
            if not self.study_session.file_search_seen:
                if self.study_session.status == 'training' and \
                                self.study_session.num_tasks_completed == 0:
                    page_tour = 'init_file_search'
                else:
                    page_tour = 'first_file_search'
        if self.task.type == 'filesystem_change':
            if not self.study_session.filesystem_change_seen:
                if self.study_session.status == 'training' and \
                                self.study_session.num_tasks_completed == 0:
                    page_tour = 'init_filesystem_change'
                else:
                    page_tour = 'first_filesystem_change'

        return page_tour


class ActionHistory(models.Model):
    """
    An action history includes the operations done by the user at a specific
    time in a task session.get

    :member task_session: The task session during which the action is taken.
    :member action: The action performed by the user, including
        - bash command issued by the user in the terminal
        - `__reset__` if the user resets the filesystem
    :member action_time: The time the action is taken.
    """
    task_session = models.ForeignKey(TaskSession, on_delete=models.CASCADE)
    action = models.TextField()
    action_time = models.DateTimeField()