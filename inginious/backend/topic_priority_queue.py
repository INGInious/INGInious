import queue
from heapq import heappush, heappop


class TopicPriorityQueue:
    """
    A simple queue which supports getting elements by topics.

    Uses python heaps behind the scenes, and thus maintains a natural ordering:
    the lowest element is returned first.

    See the heapq library for more details.
    """

    def __init__(self):
        self.queues = {}
        self.size = 0

    def __len__(self):
        return self.size

    def empty(self, topics=None):
        if topics is None:
            return self.size == 0
        for topic in topics:
            if topic in self.queues and len(self.queues[topic]) != 0:
                return False
        return True

    def put(self, topic, item):
        """
        This operation is in O(log n), where n is the size of the queue for the given topic
        """
        if topic not in self.queues:
            self.queues[topic] = []
        heappush(self.queues[topic], item)
        self.size += 1

    def get(self, topics=None):
        """
        This operation is in O(m + log n) where m is the number of topics and n the size of the queue

        :param topics: a list of topics. If None, all topics are explored.
        :return: the smallest elements that fits in one of the topics
        :raises: queue.Empty exception if the queue has no elements that fits in any of the topics
        """
        if topics is None:
            topics = self.queues.keys()

        best_topic = None
        best_elem = None
        for topic in topics:
            if (
                topic in self.queues
                and len(self.queues[topic]) != 0
                and (best_elem is None or best_elem > self.queues[topic][0])
            ):
                best_topic = topic
                best_elem = self.queues[topic][0]
        if best_topic is None:
            raise queue.Empty()
        self.size -= 1
        return heappop(self.queues[best_topic])
