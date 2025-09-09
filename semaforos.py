import math
import random
from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib import animation
from matplotlib.patches import Rectangle

# ================== Parámetros globales ==================
FPS = 30
INTERVAL = int(1000 / FPS)
random.seed(5)

COLS, ROWS = 3, 3
SPACING = 1.6
MARGIN  = 0.9

# Ventanas de reglas
D = 0.55    # antes de la línea (reglas 1 y 4)
R = 0.15    # muy cerca de la línea (regla 3)
E = 0.12    # después del cruce (reglas 5 y 6)

U_MIN_GREEN = int(1.5 * FPS)   # 2) verde mínimo
YELLOW_TIME = int(0.6 * FPS)
N_THRESHOLD = 16               # 1) umbral
M_FEW = 2                      # 3) "pocos por cruzar"

# Anti-bloqueo (regla 6)
GL_STICK       = int(0.8 * FPS)   # bloqueo sostenido para ALL_RED
FORCE_RELEASE  = int(2.5 * FPS)   # forzar salida desde ALL_RED

# Factores globales
TRAFFIC = 0.60                # sube/baja con ] / [
SPEED   = 0.80                 # sube/baja con + / -

CAR_LEN = 0.08                 # longitud virtual para espaciar


NO_STOP_AFTER = 0.28           # distancia después de la línea (≈ ancho del cruce)

# ================== Utils ==================
def pois(lam):
    if lam <= 0: return 0
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        k += 1; p *= random.random()
        if p <= L: return k-1

# ================== Entidades ==================
@dataclass
class Car:
    lane_id: tuple
    pos: float
    v: float = 0.0
    commit_to: Optional[float] = None   # coordenada hasta la que NO puede parar (zona de cruce)

class Lane:
    """Carril 1D. lane_id = ('H'|'V', idx, dir) con dir=+1 (→/↑), -1 (←/↓)."""
    def __init__(self, lane_id, start, end, fixed_coord, rate):
        self.id = lane_id
        self.start, self.end = start, end
        self.fixed = fixed_coord
        self.rate  = rate
        self.cars: list[Car] = []

    def spawn(self):
        # Poisson con espaciado mínimo
        for _ in range(pois(self.rate * TRAFFIC)):
            ok = True
            if self.cars:
                head = max(self.cars, key=lambda c: self.id[2]*c.pos) if self.id[2] > 0 \
                       else min(self.cars, key=lambda c: self.id[2]*c.pos)
                ok = abs(self.start - head.pos) > CAR_LEN * 4.0
            if ok:
                self.cars.append(Car(self.id, self.start, v=0.0))

    def sort(self):
        self.cars.sort(key=lambda c: self.id[2]*c.pos, reverse=True)

class Intersection:
    def __init__(self, x, y):
        self.xy = (x, y)
        self.state = "EW_GREEN"
        self.t = 0
        self.counter = {"EW": 0, "NS": 0}
        self.lock_frames = 0
        self.allred_frames = 0

    def colors(self):
        if self.state == "EW_GREEN":  return {"EW":"G","NS":"R"}
        if self.state == "NS_GREEN":  return {"EW":"R","NS":"G"}
        if self.state == "EW_YELLOW": return {"EW":"Y","NS":"R"}
        if self.state == "NS_YELLOW": return {"EW":"R","NS":"Y"}
        return {"EW":"R","NS":"R"}

# ================== Mundo ==================
class World:
    def __init__(self):
        self.xs = [i*SPACING for i in range(COLS)]
        self.ys = [j*SPACING for j in range(ROWS)]
        self.x_min = -MARGIN; self.x_max = self.xs[-1] + MARGIN
        self.y_min = -MARGIN; self.y_max = self.ys[-1] + MARGIN

        self.lanes = []
        for j, y in enumerate(self.ys):
            self.lanes.append(Lane(('H', j, +1), self.x_min, self.x_max, y, rate=0.08))
            self.lanes.append(Lane(('H', j, -1), self.x_max, self.x_min, y, rate=0.07))
        for i, x in enumerate(self.xs):
            self.lanes.append(Lane(('V', i, +1), self.y_min, self.y_max, x, rate=0.07))
            self.lanes.append(Lane(('V', i, -1), self.y_max, self.y_min, x, rate=0.07))

        self.lights = {(i,j): Intersection(self.xs[i], self.ys[j])
                       for i in range(COLS) for j in range(ROWS)}
        self.force_phase = 0

    # --- Geometría ---
    def stop_line(self, lane: Lane, i, j):
        x, y = self.xs[i], self.ys[j]
        if lane.id[0] == 'H':
            return x - 0.10 if lane.id[2] > 0 else x + 0.10
        else:
            return y - 0.10 if lane.id[2] > 0 else y + 0.10

    def next_intersections_on_lane(self, lane: Lane):
        if lane.id[0] == 'H':
            j = lane.id[1]
            i_list = range(COLS) if lane.id[2] > 0 else range(COLS-1, -1, -1)
            return [((i, j), self.stop_line(lane, i, j)) for i in i_list]
        else:
            i = lane.id[1]
            j_list = range(ROWS) if lane.id[2] > 0 else range(ROWS-1, -1, -1)
            return [((i, j), self.stop_line(lane, i, j)) for j in j_list]

    def get_lane(self, lane_id):
        for L in self.lanes:
            if L.id == lane_id: return L
        raise KeyError(lane_id)

    # --- Contadores por ventana ---
    def count_before_axis(self, ij, axis, dist):
        i, j = ij; c = 0
        lanes = (('H', j, +1), ('H', j, -1)) if axis == "EW" else (('V', i, +1), ('V', i, -1))
        for lane_id in lanes:
            L = self.get_lane(lane_id); stop = self.stop_line(L, i, j)
            for car in L.cars:
                d = (stop - car.pos) * L.id[2]
                if 0 <= d <= dist: c += 1
        return c

    def count_after_axis(self, ij, axis, dist, need_stopped=True):
        i, j = ij; c = 0
        lanes = (('H', j, +1), ('H', j, -1)) if axis == "EW" else (('V', i, +1), ('V', i, -1))
        for lane_id in lanes:
            L = self.get_lane(lane_id); stop = self.stop_line(L, i, j)
            for car in L.cars:
                d = (stop - car.pos) * L.id[2]
                if -dist <= d < 0:
                    if (not need_stopped) or (abs(car.v) < 1e-3):
                        c += 1
        return c

    def free_after_cell(self, ij, axis, min_gap):
        """True si hay hueco inmediato tras la línea al menos min_gap."""
        i, j = ij; best = float("inf")
        lanes = (('H', j, +1), ('H', j, -1)) if axis == "EW" else (('V', i, +1), ('V', i, -1))
        for lane_id in lanes:
            L = self.get_lane(lane_id); stop = self.stop_line(L, i, j)
            for car in L.cars:
                d = (stop - car.pos) * L.id[2]
                if -E <= d < 0:
                    best = min(best, abs(d))
        return best > min_gap

    # --- Simulación ---
    def step(self):
        # Spawns
        for L in self.lanes: L.spawn()

        # Mover coches
        for L in self.lanes:
            L.sort(); new = []
            for k, car in enumerate(L.cars):
                desired = 0.020 * SPEED
                dir_ = L.id[2]

                # Fin de compromiso 
                if car.commit_to is not None:
                    if (dir_ > 0 and car.pos >= car.commit_to) or (dir_ < 0 and car.pos <= car.commit_to):
                        car.commit_to = None  # ya salió del cruce

                gap_front = 9e9 if k == 0 else (L.cars[k-1].pos - car.pos) * dir_
                blocked = False

                # Si está comprometido a cruzar, ignora bloqueos del cruce ya pasado.
                if car.commit_to is None:
                    for (ij, stop) in self.next_intersections_on_lane(L):
                        d = (stop - car.pos) * dir_

                        # Si d <= 0, ese cruce quedó atrás: mirar el siguiente
                        if d <= 0.0:
                            continue

                        axis = "EW" if L.id[0]=='H' else "NS"
                        col = self.lights[ij].colors()[axis]

                        # rojo/amarillo: detener en la línea
                        if col in ("R","Y") and d <= CAR_LEN*1.05:
                            blocked = True; break

                        # verde: Regla 5 "smart" (no entrar si está lleno después del cruce)
                        if col == "G" and d <= CAR_LEN*1.05:
                            jam_stopped = self.count_after_axis(ij, axis, E, True)
                            if jam_stopped >= 2:
                                blocked = True
                            elif jam_stopped == 1:
                                # si no hay hueco y NO soy el primero de la fila, me detengo
                                if not self.free_after_cell(ij, axis, min_gap=CAR_LEN*1.0) and k != 0:
                                    blocked = True
                            if not blocked:
                                # *** ENTRA AL CRUCE → ACTIVAR ZONA DE NO-PARADA ***
                                car.commit_to = stop + dir_ * NO_STOP_AFTER
                            if blocked: break

                        # solo consideramos el próximo cruce hacia delante
                        break

                # movimiento con o sin compromiso
                if blocked or gap_front < CAR_LEN*1.2:
                    # Si estoy en la zona comprometida, no me quedo "pegado": avanza un mínimo
                    if car.commit_to is not None and gap_front > CAR_LEN*0.9:
                        car.v = max(0.006, 0.6 * desired)
                        car.pos += car.v * dir_
                    else:
                        car.v = 0.0
                else:
                    car.v = desired
                    car.pos += car.v * dir_

                # salir del mapa
                if (dir_ > 0 and car.pos > L.end + 0.1) or (dir_ < 0 and car.pos < L.end - 0.1):
                    continue
                new.append(car)
            L.cars = new

        # Lógica de semáforos por cruce (reglas 1–6)
        for (i,j), light in self.lights.items():
            light.t += 1

            # 6) bloqueo sostenido en ambos ejes -> ALL_RED
            both_blocked = (self.count_after_axis((i,j),"EW",E,True) > 0 and
                            self.count_after_axis((i,j),"NS",E,True) > 0)
            light.lock_frames = light.lock_frames + 1 if both_blocked else 0
            if light.lock_frames >= GL_STICK and light.state != "ALL_RED":
                light.state = "ALL_RED"; light.t = 0; light.allred_frames = 0
                continue

            # Recuperación desde ALL_RED
            if light.state == "ALL_RED":
                light.allred_frames += 1
                ew_after = self.count_after_axis((i,j),"EW",E,True)
                ns_after = self.count_after_axis((i,j),"NS",E,True)
                if ew_after == 0 and ns_after > 0:
                    light.state = "EW_GREEN"; light.t = 0; light.counter={"EW":0,"NS":0}; continue
                if ns_after == 0 and ew_after > 0:
                    light.state = "NS_GREEN"; light.t = 0; light.counter={"EW":0,"NS":0}; continue
                if ns_after == 0 and ew_after == 0:
                    axis = "NS" if self.count_before_axis((i,j),"NS",D) >= \
                                   self.count_before_axis((i,j),"EW",D) else "EW"
                    light.state = f"{axis}_GREEN"; light.t = 0; light.counter={"EW":0,"NS":0}; continue
                if light.allred_frames >= FORCE_RELEASE:
                    axis = "EW" if ((i + j + self.force_phase) % 2 == 0) else "NS"
                    light.state = f"{axis}_GREEN"; light.t = 0; light.counter={"EW":0,"NS":0}
                    self.force_phase ^= 1
                continue

            # Amarillo -> opuesto
            if "YELLOW" in light.state:
                if light.t >= YELLOW_TIME:
                    light.state = "NS_GREEN" if light.state == "EW_YELLOW" else "EW_GREEN"
                    light.t = 0; light.counter = {"EW":0,"NS":0}
                continue

            # En verde
            green_axis = "EW" if light.state == "EW_GREEN" else "NS"
            red_axis   = "NS" if green_axis == "EW" else "EW"

            # 1) acumular demanda en rojo (d)
            light.counter[red_axis] += self.count_before_axis((i,j), red_axis, D)

            # 2) mínimo verde
            if light.t < U_MIN_GREEN:
                continue

            # 5) atasco después del cruce en el eje verde (e)
            if self.count_after_axis((i,j), green_axis, E, True) > 0:
                light.state = f"{green_axis}_YELLOW"; light.t = 0; continue

            # 4) nadie por la verde (d) y sí por la roja (d)
            if self.count_before_axis((i,j), green_axis, D) == 0 and \
               self.count_before_axis((i,j), red_axis,   D) > 0:
                light.state = f"{green_axis}_YELLOW"; light.t = 0; continue

            # 1) + 3) umbral n salvo pocos a r
            if light.counter[red_axis] >= N_THRESHOLD:
                near_green = self.count_before_axis((i,j), green_axis, R)
                if 0 < near_green <= M_FEW:
                    pass
                else:
                    light.state = f"{green_axis}_YELLOW"; light.t = 0; continue

# ================== Dibujo ==================
def make_fig(world: World):
    W, H = world.xs[-1]+MARGIN, world.ys[-1]+MARGIN
    fig, ax = plt.subplots(figsize=(6.2,6.2))
    ax.set_aspect('equal'); ax.set_xlim(-MARGIN, W); ax.set_ylim(-MARGIN, H)
    ax.axis('off')
    ax.add_patch(Rectangle((-MARGIN,-MARGIN), W+MARGIN, H+MARGIN, color="#d9c8b8"))
    for y in world.ys: ax.add_patch(Rectangle((-MARGIN, y-0.15), W+MARGIN, 0.30, color="white"))
    for x in world.xs: ax.add_patch(Rectangle((x-0.15, -MARGIN), 0.30, H+MARGIN, color="white"))
    return fig, ax

def draw_frame(ax, world: World, dots, tiles, txt):
    for (i,j), light in world.lights.items():
        col = light.colors(); x, y = world.xs[i], world.ys[j]; size = 0.14
        c_ew = {"G":"#3CCB3C","R":"#E23B3B","Y":"#E5C02A"}[col["EW"]]
        c_ns = {"G":"#3CCB3C","R":"#E23B3B","Y":"#E5C02A"}[col["NS"]]
        tiles[(i,j,"E")].set_xy((x+0.01, y+0.01));          tiles[(i,j,"E")].set_color(c_ew)
        tiles[(i,j,"W")].set_xy((x-0.01-size, y-0.01-size)); tiles[(i,j,"W")].set_color(c_ew)
        tiles[(i,j,"N")].set_xy((x-0.01-size, y+0.01));     tiles[(i,j,"N")].set_color(c_ns)
        tiles[(i,j,"S")].set_xy((x+0.01, y-0.01-size));     tiles[(i,j,"S")].set_color(c_ns)

    for p in dots: p.remove()
    dots.clear()
    for L in world.lanes:
        for c in L.cars:
            if L.id[0]=='H':
                x, y = c.pos, L.fixed + (0.05 if L.id[2]>0 else -0.05)
            else:
                x, y = L.fixed + (0.05 if L.id[2]>0 else -0.05), c.pos
            dots.append(ax.plot(x, y, 'o', ms=4, mfc='#02b7d9', mec='#016a7a', zorder=10)[0])

    txt.set_text(f"traf={TRAFFIC:.2f}  vel={SPEED:.2f}")

# ================== Animación ==================
def main():
    global TRAFFIC, SPEED
    world = World()
    fig, ax = make_fig(world)

    tiles = {}
    for (i,j) in world.lights.keys():
        for k in ("E","W","N","S"):
            r = Rectangle((0,0), 0.14, 0.14, color="#3CCB3C", zorder=5)
            ax.add_patch(r); tiles[(i,j,k)] = r

    dots = []
    txt = ax.text(0.02, 0.98, "", transform=ax.transAxes, ha="left", va="top", color="#333", fontsize=10)

    paused = {"v": False}
    def on_key(e):
        nonlocal paused
        global TRAFFIC, SPEED
        if e.key == " ": paused["v"] = not paused["v"]
        elif e.key == "]": TRAFFIC = min(1.5, TRAFFIC * 1.1)
        elif e.key == "[": TRAFFIC = max(0.05, TRAFFIC / 1.1)
        elif e.key in ("+", "="): SPEED = min(1.2, SPEED + 0.05)
        elif e.key in ("-", "_"): SPEED = max(0.10, SPEED - 0.05)
    fig.canvas.mpl_connect("key_press_event", on_key)

    def update(_):
        if not paused["v"]:
            world.step()
        draw_frame(ax, world, dots, tiles, txt)
        return dots + list(tiles.values()) + [txt]

    anim = animation.FuncAnimation(fig, update, interval=INTERVAL, blit=False, cache_frame_data=False)
    fig._anim = anim
    plt.show()

if __name__ == "__main__":
    main()
