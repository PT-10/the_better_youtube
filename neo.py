import config 
from py2neo import Graph, Node, Relationship
import numpy as np
from mysql import get_clicks

graph = Graph("bolt://localhost:7687", auth=(config.neo4j_user, config.neo4j_pass))


class User:
    def __init__(self, username):
        self.username = username
    
    def register(self):
        if not self.find():
            user = Node('User', username=self.username)
            graph.create(user)
            return True
        else:
            return False

    def find(self):
        user = graph.nodes.match('User', 'username', self.username).first()
        return user

    def subscribe(self, channel_name):
        if not self.is_subscribed(channel_name):
            Channel(channel_name).subscribe(self.find())
            return True
        return False

    def is_subscribed(self, channel_name):
        query = """
        MATCH (n:User)-[r]-(v:Channel)
        WHERE n.username="{}" and v.channelId="{}"
        RETURN COUNT(r) as count
        """
        return graph.run(query.format(self.find()['username'],channel_name).data()[0]['count'])

    def unsubscribe(self, channel_name):
        query = """
        MATCH (n:User)-[r]-(v:Channel)
        WHERE n.username="{}" and v.channelId="{}"
        DELETE r
        """
        graph.run(query.format(self.find()['username'],channel_name))

    def like_video(self, video_id):
        user = self.find()
        Video(video_id).like(user)

    def dislike_video(self, video_id):
        user = self.find()
        Video(video_id).dislike(user)

    def is_liked_video(self, video_id):
        query = """
        MATCH (n:User)-[r:Likes]-(v:Video)
        WHERE n.username="{}" and v.videoId="{}"
        RETURN COUNT(r) as count
        """
        return graph.run(query.format(self.find()['username'],video_id)).data()[0]['count']

    def is_disliked_video(self, video_id):
        query = """
        MATCH (n:User)-[r:Dislikes]-(v:Video)
        WHERE n.username="{}" and v.videoId="{}"
        RETURN COUNT(r) as count
        """
        return graph.run(query.format(self.find()['username'],video_id)).data()[0]['count']

    def clear_rel_with_video(self, video_id):
        user = self.find()
        Video(video_id).clear_user_rel(user)

    def liked_videos(self):
        query = '''
        MATCH (user:User)-[:Likes]-(video:Video)
        WHERE user.username = "{}"
        RETURN DISTINCT video.mongoId
        '''
        return graph.run(query.format(self.username)).data()

    def disliked_videos(self):
        query = '''
        MATCH (user:User)-[:Dislikes]-(video:Video)
        WHERE user.username = "{}"
        RETURN DISTINCT video.mongoId
        '''
        return graph.run(query.format(self.username)).data()


class Channel:

    def __init__(self, channel_name):
        self.name = channel_name
    
    def insert_channel(self,chanelId):
        if self.find():
            return False
        channel = Node('Channel', channelId=chanelId)
        graph.create(channel)
        return True

    def find(self):
        channel = graph.nodes.match('Channel', channelId=self.name).first()
        return channel

    def subscribers(self):
        query = '''
        MATCH (user:User)-[:Subscriber]-(channel:Channel)
        WHERE channel.channelId = "{}"
        RETURN DISTINCT user.username
        '''
        return graph.run(query.format(self.name))

    def subscriber_count(self):
        query = '''
        MATCH (user:User)-[:Subscriber]-(channel:Channel)
        WHERE channel.channelId = "{}"
        RETURN COUNT(DISTINCT user)
        '''
        return graph.run(query.format(self.name))

    def video_count(self):
        query = '''
        MATCH (video:Video)-[:HasChannel]-(channel:Channel)
        WHERE channel.channelId = "{}"
        RETURN COUNT(DISTINCT video)
        '''
        return graph.run(query.format(self.name))

    def videos(self):
        query = '''
        MATCH (video:Video)-[:HasChannel]-(channel:Channel)
        WHERE channel.channelId = "{}"
        RETURN DISTINCT video.videoId
        '''
        return graph.run(query.format(self.name))

    def add_video(self, video):
        graph.create(Relationship(video, "HasChannel", self.find()))
    def subscribe(self, user):
        graph.create(Relationship(user, "Subscriber", self.find()))


class Video:

    def __init__(self, id_):
        self.id = id_
    
    def insert_video(self,mongoid,title,description,channelId,channelTitle,tags,title_embeddings,desc_embeddings=None):
        if self.find():
            return False
        video = Node('Video', videoId=self.id, mongoId=mongoid, title=title, description=description, channelId=channelId, channelTitle=channelTitle,tags=tags,title_embeddings=title_embeddings,desc_embeddings=desc_embeddings)
        graph.create(video)
        return True


    def find(self):
        video = graph.nodes.match('Video', videoId=self.id).first()
        return video
    
    def get_channel(self):
        query = '''
        MATCH (video:Video)-[:HasChannel]-(channel:Channel)
        WHERE video.videoId = "{}"
        RETURN DISTINCT channel.channelId
        '''
        if len(graph.run(query.format(self.id)).data()) == 0:
            return None
        return graph.run(query.format(self.id)).data()[0]['channel.channelId']

    def liked_by(self):
        query = '''
        MATCH (user:User)-[:Likes]-(video:Video)
        WHERE video.videoId = "{}"
        RETURN DISTINCT user.username
        '''
        return graph.run(query.format(self.id))

    def liked_by_count(self):
        query = '''
        MATCH (user:User)-[:Likes]-(video:Video)
        WHERE video.videoId = "{}"
        RETURN COUNT(DISTINCT user.username) as count
        '''
        return graph.run(query.format(self.id)).data()[0]['count']

    def disliked_by(self):
        query = '''
        MATCH (user:User)-[:Dislikes]-(video:Video)
        WHERE video.videoId = "{}"
        RETURN DISTINCT user.username
        '''
        return graph.run(query.format(self.id))

    def disliked_by_count(self):
        query = '''
        MATCH (user:User)-[:Dislikes]-(video:Video)
        WHERE video.videoId = "{}"
        RETURN COUNT(DISTINCT user.username) as count
        '''
        return graph.run(query.format(self.id)).data()[0]['count']

    def like(self, user):
        self.clear_user_rel(user)
        graph.create(Relationship(user, "Likes", self.find()))

    def dislike(self, user):
        self.clear_user_rel(user)
        graph.create(Relationship(user, "Dislikes", self.find()))

    def clear_user_rel(self, user):
        query = """
        MATCH (n:User)-[r]-(v:Video)
        WHERE n.username="{}" and v.videoId="{}"
        DELETE r
        """
        graph.run(query.format(user['username'],self.find()['videoId']))

    def add_related_video(self, video):
        if video.find() == None:
            return
        current_channel = self.get_channel()
        related_channel = video.get_channel()
        same_channel = False
        if current_channel == related_channel:
            print('same  channel')
            same_channel = True
        common_tags=0
        if 'tags' in self.find() and 'tags' in video.find():
            common_tags = len(set(self.find()['tags']).intersection(set(video.find()['tags'])))
        # common_description = commonDescription(self.find()['desc_embeddings'], video.find()['desc_embeddings'])
        common_title = commonTitle(self.find()['title_embeddings'], video.find()['title_embeddings'])
        if same_channel:
            similarity = 0.5 * common_tags+ 0.25 * common_title
        else:
            similarity = 0.375 * common_tags+ 0.25* common_title
        graph.create(Relationship(self.find(), "Related", video.find(),weight=similarity))
        

def commonDescription(x, y):
    return int(cosine_similarity(x, y))

def commonTitle(x, y):
    return int(cosine_similarity(x, y))

def cosine_similarity(vector_a, vector_b):
    dot_product = np.dot(vector_a, vector_b)
    magnitude_a = np.linalg.norm(vector_a)
    magnitude_b = np.linalg.norm(vector_b)
    similarity = dot_product / (magnitude_a * magnitude_b)
    return similarity


def get_related_videos(video_id):
    query = '''
    MATCH (video:Video)-[r:Related]-(related:Video)
    WHERE video.videoId = "{}"
    RETURN related
    ORDER BY r.weight DESC
    LIMIT 10
    '''
    return graph.run(query.format(video_id)).data()


def get_ordered_related_videos(user_id,video_id):
    # Get related videos from Neo4j
    related_videos = get_related_videos(video_id)
    print(related_videos[0]['related'].get('videoId'))
    related_videos = [(video['related'].get('videoId'),get_clicks(user_id,video['related'].get('videoId'))) for video in related_videos]
    # Order videos by clicks
    ordered_videos = sorted(related_videos, key=lambda x: x[1], reverse=True)
    ordered_videos=[video[0] for video in ordered_videos]

    return ordered_videos

if __name__ == '__main__':
    print(get_ordered_related_videos('akhil','_WakZETpKo0'))
