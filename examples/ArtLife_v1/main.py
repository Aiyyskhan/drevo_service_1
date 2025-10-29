import sys
import math
import numpy as np
import pygame
from PIL import Image
from settings import *
from player_base import Player
from map_file_lev0_2 import get_map
from drawing import Drawing
from ray_casting import RayCast
import genetic_algorithm as ga
import neural_network as nn
from genome_uploader import upload

ORIGIN_MODE = False # False если эволюция инициируется от сохраненных родителей
SAVING_WINNER = True

VAL = np.linspace(-1, 1, 256) #9)


def weight_ids_matrix_build(pop_size,num_inputs, num_hiddens, num_outputs):
    pop_weight_indices_matrix_list = []
    for _ in range(pop_size):
        weight_indices_matrix_list = []
        weight_indices_matrix_list.append(np.random.randint(0, 256, size=(num_inputs, num_hiddens)).astype(np.uint8))
        weight_indices_matrix_list.append(np.random.randint(0, 256, size=(num_hiddens, num_hiddens)).astype(np.uint8))
        weight_indices_matrix_list.append(np.random.randint(0, 256, size=(num_hiddens, num_outputs)).astype(np.uint8))
        pop_weight_indices_matrix_list.append(weight_indices_matrix_list)
    return pop_weight_indices_matrix_list

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
    # w_ids = (np.array(frame) / 255.0) * 8.0
    w_ids = np.array(frame)

    # print(f"png2arr: {w_ids.shape}")
        
    w_ids = np.rot90(w_ids, axes=(2,0))

    w_id_0 = np.rot90(w_ids[0], axes=(0,1)).astype(np.uint16)
    w_id_1 = np.rot90(w_ids[1], k=2, axes=(0,1)).astype(np.uint16)
    w_id_2 = np.rot90(w_ids[2], k=3, axes=(0,1)).astype(np.uint16)
    # w_id_0 = w_ids[0].copy().astype(np.uint16)
    # w_id_1 = w_ids[1].copy().astype(np.uint16)
    # w_id_2 = w_ids[2].copy().astype(np.uint16)

    # print(f"w_id_0: {w_id_0.shape}")
    # print(f"w_id_0 type: {w_id_0.dtype}")
    # print(f"w_id_0: {w_id_0[:5,:5]}")
    # print(f"w_id_1: {w_id_1.shape}")
    # print(f"w_id_1: {w_id_1[:5,:5]}")
    # print(f"w_id_2: {w_id_2.shape}")
    # print(f"w_id_2: {w_id_2[:5,:5]}")

    w_id = np.around((w_id_0 + w_id_1 + w_id_2) // 3.0).astype(np.uint8)

    # print(f"w_id: {w_id.shape}")
    # print(f"w_id: {w_id[:5,:5]}")

    i_w_id = w_id[:5, :50]
    h_w_id = w_id[5:, :50]
    o_w_id = w_id[5:, 50:53]

    # return (
    #     val[i_w_id], 
    #     val[h_w_id], 
    #     val[o_w_id]
    # )
    return [i_w_id, h_w_id, o_w_id]

def arr2png(i_w_id, h_w_id, o_w_id): #, path):
    w_id = np.zeros((55, 55), dtype=np.uint8)
    w_id[:5, :50] = i_w_id
    w_id[5:, :50] = h_w_id
    w_id[5:, 50:53] = o_w_id

    # a = np.full_like(w_id, 255, dtype=np.uint8)

    w_id_0 = np.rot90(w_id, axes=(1,0))
    w_id_1 = np.rot90(w_id, k=2, axes=(1,0))
    w_id_2 = np.rot90(w_id, k=3, axes=(1,0))
    # w_id_0 = w_id.copy()
    # w_id_1 = w_id.copy()
    # w_id_2 = w_id.copy()

    w_ids = np.stack([w_id_0, w_id_1, w_id_2])
    w_ids = np.rot90(w_ids, axes=(0,2))

    img_arr = w_ids.astype(np.uint8)

    # print(f"arr2png: {img_arr.shape}")
    # print(f"img_arr_to_png: {img_arr}")

    return Image.fromarray(img_arr)

def gif2arr(path):
    im = Image.open(path)
    return [png2arr(frame) for frame in iter_frames(im)]

def arr2gif(weight_list, path):
    imgs = []
    for i in range(len(weight_list)):
        imgs.append(arr2png(weight_list[i][0], weight_list[i][1], weight_list[i][2]))

    # Сохраняем в GIF
    imgs[0].save(
        path,
        save_all=True,
        append_images=imgs[1:],  # остальные кадры
        duration=200,              # время одного кадра (мс)
        loop=0                     # бесконечный цикл
    )

class Game:
    def __init__(self):
        # генерация случайных цветов для особей
        self.color_r = np.random.randint(50, 220, NUM_PLAYERS) #np.linspace(126, 194, NUM_PLAYERS).astype(int)
        self.color_g = np.random.randint(50, 220, NUM_PLAYERS) #np.linspace(130, 114, NUM_PLAYERS).astype(int)
        self.color_b = np.random.randint(50, 220, NUM_PLAYERS) #np.linspace(45, 29, NUM_PLAYERS).astype(int)

        self.game_over = False
        self.generation = 1
        self.epoch = 0
        self.max_epoch = 20000
        
        self.number_of_live_players = NUM_PLAYERS
        self.number_of_winners = 0

        self.mutation_time = False

        self.best_players = []
        self.best_player_reward = 0.0

        # основные пути загрузки родителей и сохранения финишеров
        self.main_load_path = "genomes/20250921/leaders_5.50.3_2_1_best.gif" #"data/genomes/leaders_5.3.50_2.gif"
        self.main_save_path = "genomes/20251029/"

        self.save_number = 0
        self.load_number = 0

        pygame.init()
        self.sc = pygame.display.set_mode((WIDTH, HEIGHT))
        self.sc_map = pygame.Surface((WIDTH // MAP_SCALE, HEIGHT // MAP_SCALE))
        self.clock = pygame.time.Clock()
        self.drawing = Drawing(self.sc, self.sc_map)

        # данные игровой карты
        self.finish_coords = set()
        self.wall_coord_list = list()
        self.world_map, self.collision_walls = get_map(TILE)
        for coord, signature in self.world_map.items():
            if signature == "1":
                self.wall_coord_list.append(coord)
            elif signature == "2":
                self.finish_coords.add(coord)

        self.nn_parameters = (NUM_RAYS, 50, 3)
        self.weight_ids_matrix_list = []
        self.pop_weight_list = []
        if ORIGIN_MODE:
            self.weight_ids_matrix_list = weight_ids_matrix_build(NUM_PLAYERS, self.nn_parameters[0], self.nn_parameters[1], self.nn_parameters[2])
        else:
            self.loading(self.main_load_path)

        self.num_individuals = len(self.weight_ids_matrix_list)
        print(f"Population size: {self.num_individuals}")
        self.number_of_live_players = self.num_individuals

        self.population_build()

        self.running = True
    
    def population_build(self):
        self.pop_weight_list = []
        for ind_w_ids_matrices in self.weight_ids_matrix_list:
            weight_list = []
            for w_ids_matrix in ind_w_ids_matrices:
                # w_ids_matrix = np.clip((w_ids_matrix / 255.0) * 8.0, 0, 255).astype(np.uint8)
                weight_list.append(VAL[w_ids_matrix])
            self.pop_weight_list.append(weight_list)

        # каждая особь популяции имеет свой начальный угол поворота
        self.angle_diff = 360 // self.num_individuals
        self.players = []
        
        # создание игроков - особей популяции
        for i, w_list in enumerate(self.pop_weight_list):
            player = Player(self.sc, self.collision_walls, self.finish_coords)
            player.color = (self.color_r[i], self.color_g[i], self.color_b[i])
            player.init_angle = math.pi + (math.pi/2) #self.angle_diff * i
            player.rays = RayCast(self.world_map)
            player.brain = nn.NNet()
            player.brain.weight_list = w_list
            player.setup()
            self.players.append(player)

    def game_event(self):
        # drawing.background()
        for player in self.players:
            if player.dead and not player.verified:
                self.number_of_live_players -= 1
                player.verified = True
            else:
                player.movement()
                player.draw()

            if player.reached_finish=="y":
                player.reached_finish = "v"
                self.number_of_winners += 1
                self.best_player_reward = 0.0
        
        for x, y in self.wall_coord_list:
            pygame.draw.rect(self.sc, WALL_COLOR_1, (x, y, TILE, TILE), 2)
        for x, y in self.finish_coords:
            pygame.draw.rect(self.sc, WALL_COLOR_2, (x, y, TILE, TILE), 2)

        self.drawing.info(self.generation, self.number_of_winners, self.number_of_live_players, self.clock)

    def stop_function(self):
        if self.number_of_live_players == 0 or self.epoch >= self.max_epoch:
            self.game_over = True
            self.epoch = 0
        if self.game_over and self.number_of_live_players > 0:
            winners = []
            for idx, player in enumerate(self.players):
                if not player.dead and player.reached_finish == "v":
                    # self.saving(player)
                    winners.append(self.weight_ids_matrix_list[idx])
                    # self.number_of_winners += 1
                    self.best_player_reward = 0.0
            if len(winners) > 0:
                path = f"{self.main_save_path}leaders_{self.nn_parameters[0]}.{self.nn_parameters[1]}.{self.nn_parameters[2]}_{self.generation}_{self.save_number}.gif"
                self.saving(path, winners)
                #self.running = False

    def saving(self, path, weight_idx_list):
        arr2gif(weight_idx_list, path)

        self.save_number += 1

    def loading(self, path):
        self.weight_ids_matrix_list = gif2arr(path)
            
    def evolution(self):
        result_list = []
        parent_weight_list = []
        winners = []

        leader_weights = None
        child_weights = None

        for player in self.players:
            result_list.append(player.reward)

        if SAVING_WINNER:
            for idx, player in enumerate(self.players):
                if player.reached_finish == "v":
                    winners.append(self.weight_ids_matrix_list[idx])
            if len(winners) > 0:
                path = f"{self.main_save_path}leaders_{self.nn_parameters[0]}.{self.nn_parameters[1]}.{self.nn_parameters[2]}_{self.generation}_{self.save_number}.gif"
                self.saving(path, winners)
                print(f"✅ Saved: {path}")
                
                upload(path)

                self.running = False

        if max(result_list) >= self.best_player_reward:
            self.best_players = self.players.copy()
            self.best_player_reward = max(result_list)
            self.generation += 1

        else:
            self.players = self.best_players.copy()
            result_list.clear()
            for player in self.players:
                result_list.append(player.reward)    

        parent_weight_list = self.weight_ids_matrix_list.copy()

        if not self.mutation_time:
            num_leaders = NUM_WINNERS if NUM_WINNERS <= len(parent_weight_list) else len(parent_weight_list)
            leader_weights = ga.selection(parent_weight_list, result_list.copy(), num_leaders, True)
                
            child_weights = ga.crossover(leader_weights, NUM_PLAYERS)
            
            self.mutation_time = True
        else:
            child_weights = parent_weight_list.copy()
            child_weights = ga.mutation(child_weights)
            
            self.mutation_time = False

        self.weight_ids_matrix_list = child_weights.copy()

        self.population_build()
                
        self.number_of_live_players = NUM_PLAYERS
        self.game_over = False


    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    exit()
            self.sc.fill(BLACK)

            if not self.game_over:
                self.game_event()
                self.stop_function()
            else:
                self.evolution()

            pygame.display.flip()
            self.clock.tick()
            self.epoch += 1
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()