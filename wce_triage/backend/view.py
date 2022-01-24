
class View(object):


    def update(self, t0: dict, t1: dict):
        point_a = set(t0.items())
        point_b = set(t1.items())
        removed = point_a - point_b
        added = point_b - point_a
        pass
    
