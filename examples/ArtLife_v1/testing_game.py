import math
import numpy as np
import pygame
from PIL import Image
from settings import *
from player_for_testing_game import Player
from map_file_lev0_2 import get_map
from drawing import Drawing
from ray_casting import RayCast
import neural_network as g

def iter_frames(im):
    try:
        i = 0
        while 1:
            im.seek(i)
            yield im.copy().convert("RGBA")
            i += 1
    except EOFError:
        pass
    
def png2arr(frame): #, val):
    w_ids = (np.array(frame) / 255.0) * 8.0
    # w_ids = np.array(frame)
        
    w_ids = np.rot90(w_ids, axes=(2,0))

    w_id_0 = np.rot90(w_ids[0], axes=(0,1))
    w_id_1 = np.rot90(w_ids[1], k=2, axes=(0,1))
    w_id_2 = np.rot90(w_ids[2], k=3, axes=(0,1))

    w_id = np.around((w_id_0 + w_id_1 + w_id_2) / 3.0).astype(np.uint8)
    # w_id = np.clip((w_id_0 + w_id_1 + w_id_2) / 3.0, 0, 255).astype(np.uint8)

    i_w_id = w_id[:5, :50]
    h_w_id = w_id[5:, :50]
    o_w_id = w_id[5:, 50:53]

    # return (
    #     val[i_w_id], 
    #     val[h_w_id], 
    #     val[o_w_id]
    # )
    return (i_w_id, h_w_id, o_w_id)

def arr2png(i_w_id, h_w_id, o_w_id): #, path):
    w_id = np.zeros((55, 55), dtype=np.uint8)
    w_id[:5, :50] = i_w_id
    w_id[5:, :50] = h_w_id
    w_id[5:, 50:53] = o_w_id

    # a = np.full_like(w_id, 255, dtype=np.uint8)

    w_id_0 = np.rot90(w_id, axes=(1,0))
    w_id_1 = np.rot90(w_id, k=2, axes=(1,0))
    w_id_2 = np.rot90(w_id, k=3, axes=(1,0))

    w_ids = np.stack([w_id_0, w_id_1, w_id_2])
    w_ids = np.rot90(w_ids, axes=(0,2))

    img_arr = w_ids.astype(np.uint8)

    return Image.fromarray(img_arr)

def gif2arr(path):
    im = Image.open(path)
    return [png2arr(frame) for frame in iter_frames(im)]

class Game:
    def __init__(self):
        self.color_r = np.random.randint(50, 220, NUM_PLAYERS)
        self.color_g = np.random.randint(50, 220, NUM_PLAYERS)
        self.color_b = np.random.randint(50, 220, NUM_PLAYERS)

        pygame.init()
        self.sc = pygame.display.set_mode((WIDTH, HEIGHT))
        self.sc_map = pygame.Surface((WIDTH // MAP_SCALE, HEIGHT // MAP_SCALE))
        self.clock = pygame.time.Clock()
        self.drawing = Drawing(self.sc, self.sc_map)

        self.road_coords = set()
        self.finish_coords = set()
        self.wall_coord_list = list()
        self.world_map, self.collision_walls = get_map(TILE)
        for coord, signature in self.world_map.items():
            if signature == "1":
                self.wall_coord_list.append(coord)
            elif signature == "2":
                self.finish_coords.add(coord)
            elif signature == ".":
                self.road_coords.add(coord)

        self.main_load_path = "data/genomes/leaders_5.3.50_6.gif"
        self.main_save_path = "data/genomes/"
        self.save_number = 4
        self.load_number = 0

        self.angle_diff = 360 // NUM_PLAYERS
        self.players = []

        self.number_of_live_players = NUM_PLAYERS

    def player_setup(self):
        for i in range(NUM_PLAYERS):
            player = Player(self.sc, self.collision_walls, self.finish_coords)
            player.color = (self.color_r[i], self.color_g[i], self.color_b[i])
            player.init_angle = math.pi + (math.pi/2) #self.angle_diff * i
            player.rays = RayCast(self.world_map)
            player.brain = g.NNet(NUM_RAYS, 3, 50)
            player.brain.weight_idx_build()
            player.brain.weight_init()
            player.setup()
            self.players.append(player)

        self.loading(self.main_load_path)


    def game_event(self):
        # drawing.background()
        for player in self.players:
            player.movement()
            player.draw()
        
        for x, y in self.wall_coord_list:
            pygame.draw.rect(self.sc, WALL_COLOR_1, (x, y, TILE, TILE), 2)
        for x, y in self.finish_coords:
            pygame.draw.rect(self.sc, WALL_COLOR_2, (x, y, TILE, TILE), 2)

        self.drawing.info(0, 0, self.number_of_live_players, self.clock)

    def loading(self, path):
        weight_idx_list = gif2arr(path)
        num_leaders = len(weight_idx_list)
        self.number_of_live_players = num_leaders
        print(f"Loaded: {path} {num_leaders} weight arrays")

        for i in range(num_leaders):
            self.players[i].brain = g.NNet(NUM_RAYS, 3, 50)
            self.players[i].brain.weight_idx_set(weight_idx_list[i])
            self.players[i].brain.weight_init()

        for player in self.players[num_leaders:]:
            player.dead = True
            player.verified = True

    def run(self):
        self.player_setup()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit()
            self.sc.fill(BLACK)

            self.game_event()

            pygame.display.flip()
            self.clock.tick()


if __name__ == "__main__":
    game = Game()
    game.run()