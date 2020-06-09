from rq import Queue
from worker import conn
import utils

q = Queue(connection=conn)

list_of_things = ['http://heroku.com', 'http://bbc.co.uk']

result = q.enqueue(utils.count_words_at_url, list_of_things)
result2 = q.enqueue(utils.print_stuff, list_of_things)

print(result)
print(result2)


