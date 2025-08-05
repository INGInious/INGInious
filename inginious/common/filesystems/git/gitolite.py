import logging
import re

from pygit2 import Signature

from inginious.common.filesystems.git.utils import MyRepo, get_rc
from inginious.common.base import GitInfo

logger = logging.getLogger("inginious.common.filesystems.git.gitolite")

class Gitolite(MyRepo):
    """ A wrapper around a gitolite-admin repository.

        Course's content is defined as a gitolite group with the 'course' prefix, e.g., '@course_test_course'.
        This group contains each repository composing the given course, i.e., tasks and $common directory.

        For example, a course 'test_course' containing two tasks 'task0' and 'task1' with 'user' administrator is configured as follows:
        ```console
        @course_test_course = test_course test_course/task0 test_course/task1 test_course/.common

        repo @course_test_course
            RW+ = superadmin user1
        ```

        The instance administrator, e.g., 'superadmin', always has access to each repository.
    """

    @classmethod
    def _is_course(cls, courseid: str, entry: str) -> bool:
        """ Determine whether current `entry` represents the course with `courseid`.
            :param entry: The entry to verify.
            :param courseid: The course identifier expected in `entry`.
            :return: True if `courseid` identifies `entry`, else False.
            
        """
        return (m := re.match('^@course_[a-z0-9_]*', entry)) is not None and m.group()[8:] == courseid

    @classmethod
    def _update_course_entry(cls, config: str, cb, courseid: str, taskid: str=None) -> list:
        """ Parse gitolite configuration and update the course configuration entry
            identified by `courseid`, and optionnaly for `taskid`.
            The actual content to add is returned by cb(line, courseid, taskid),
            where line is the configuration line to update.
            :param fd: The file descriptor pointing towards the configuration.
            :param cb: A callback function taking as argument the configuration line to update.
                       It returns the updated line, or None if it is unmodified.
            :param courseid: The course identifier whose entry has to be modified.
            :param taskid: The optionnal task identifier whose entry has to be modified.
            :return: The updated configuration content, line by line, in a list.
        """
        content = []
        # Sanity check: is the course group already defined?
        for line in config.splitlines():
            # Search for course group definition
            if cls._is_course(courseid, line):
                if (update := cb(line, courseid, taskid)) is None:
                    return None
                else:
                    line = update
            content.append(line)
        return content
        
    @classmethod
    def _add_course_content(cls, config: str, admin: str, courseid: str, taskid: str=None) -> str:
        # If course is already defined, we skip the update.
        if (content := cls._update_course_entry(
            config, lambda line, courseid, taskid: None, courseid, None
        )) is None: return None
        
        # Course not found, add it with default $common submodule.
        tasks = f'@course_{courseid} = {courseid} {courseid}/.common'
        course_entry = f'repo @course_{courseid}\n    RW+ = {admin}'
        return f'{'\n'.join(content)}\n{tasks}\n{course_entry}'

    @classmethod
    def _add_task_content(cls, config: str, admin: str, courseid:str, taskid: str) -> str:
        def _cb(line, courseid, taskid):
            tasks = line.split(' = ')[-1].split(' ')
            taskid = f'{courseid}/{taskid}'
            return None if taskid in tasks else f'{line} {taskid}'
        if (content := cls._update_course_entry(config, _cb, courseid, taskid)) is None:
            return None
        else:
            return '\n'.join(content)
   
    def init_repo(self, user: GitInfo, courseid: str, taskid: str=None, push: bool=True) -> None:
        """ Initialize a new repository on the remote Gitolite instance.
            :param user: The user initializing the repository.
            :param courseid: The course to initialize on the remote.
            :param taskid: Optionnal task to initialize within `courseid` course.
            :param push: Whether the configuration should be pushed to the remote
                Gitolite instance. Defaults to True, False is mainly used for tests.
        """

        logger.info(f"User <{user.username}> is initializing a remote repository for course <{courseid}>{' task <'+taskid+'>' if taskid is not None else ''}.")

        (user_sig, rc) = get_rc(user)
        if rc is None: logger.warning(f"Could not get credentials for User <{user.username}>, the repository will not be pushed to the remote.")

        # Early sanity check
        if 'gitolite-admin' in courseid or (taskid is not None and 'gitolite-admin' in taskid):
            logger.warn(f'Something nasty is happening, User <{user.username}> tries to modify the gitolite-admin repository. Skipping!')
            return

        # Build configuration file path.
        conf = 'conf/gitolite.conf'
        fp = f'{re.sub('/.git', '', self.path)}/{conf}'
    
        # Read old configuration and dump new configuration
        get_content = self.__class__._add_course_content if taskid is None else self.__class__._add_task_content
        with open(fp, 'r') as fd:
            content = get_content(fd.read(), user.username, courseid, taskid)

        # Sanity checks
        if content is None:
            # Configuration unchanged because the repo we are creating is already defined in the configuration.
            logging.warning('Gitolite-admin configuration unchanged. Skipping!')
            return

        if 'gitolite-admin' not in content:
            # Ensure that gitolite administration repository has not been removed.
            logger.error('gitolite-admin is not present in configuration, something bad happened. Skipping!')
            return

        # Write new configuration
        with open(fp, 'w') as fd:
            fd.write(content)
        self.index.add(conf)
        self.index.write()
        added = '' if taskid is None else f': Task <{taskid}>'
        msg = f'Course <{courseid}>{added} created.'
        self._try_commit(user_sig, msg)
        logger.info("New gitolite-admin configuration written.")

        # Push configuration to remote to actually create the remote repository.
        if push and rc is not None:
            self._try_push('origin', rc, logger=logger)
