import pygame
from settings import *
# from map_file import get_map

class Drawing:
    def __init__(self, sc, sc_map):
        self.sc = sc
        self.sc_map = sc_map
        self.font = pygame.font.SysFont('Arial', 20, bold=False)

    def background(self):
        pygame.draw.rect(self.sc, BACK_COLOR_1, (0, 0, WIDTH, HEIGHT))
        # pygame.draw.rect(self.sc, DARKGRAY, (0, HALF_HEIGHT, WIDTH, HALF_HEIGHT))

    def info(self, num_generation, num_winners, num_live_players, clock):
        render = self.font.render(f"Generation: {int(num_generation)}", 0, TEXT_COLOR_1)
        self.sc.blit(render, GENERATION_INFO_POS)
        render = self.font.render(f"Winners: {int(num_winners)}", 0, TEXT_COLOR_1)
        self.sc.blit(render, NUM_WINNERS_INFO_POS)
        render = self.font.render(f"Players: {int(num_live_players)}", 0, TEXT_COLOR_1)
        self.sc.blit(render, NUM_PLAYERS_INFO_POS)
        # render = self.font.render(f"FPS: {int(clock.get_fps())}", 0, TEXT_COLOR_1)
        # self.sc.blit(render, FPS_INFO_POS)