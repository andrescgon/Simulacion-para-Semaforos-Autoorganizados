# Integrantes :
+ Andres Castro Gonzalez
+ Juan Felipe Hurtado Herrera
+ Franco Sebastian Comas Rey
  
# Simulación de Semáforos Auto-Organizantes (Grid 3×3)
  
Este proyecto implementa una simulación 2D de un entramado 3×3 de intersecciones con semáforos auto-organizantes y generación estocástica de vehículos.
El control semafórico sigue las 6 reglas del esquema “Semáforos Auto-Organizantes”.

#Requisitos

+ Python 3.10+
+ matplotlib


# Controles en tiempo real

+ Espacio: Pausar / reanudar.
+ ] : Aumentar el tráfico (tasa de aparición de autos).
+ [ : Disminuir el tráfico.
+ '+' : Aumentar la velocidad de los autos.
+ '-' : Disminuir la velocidad de los autos.

En la esquina superior izquierda se muestra traf= (intensidad de tráfico) y vel= (escala de velocidad).

Parámetros principales (en la cabecera del archivo)

+ COLS, ROWS → tamaño de la rejilla (por defecto 3×3).

# Ventanas de reglas

+ D = 0.55 → distancia antes de la línea para Reglas 1 y 4 (d).
+ R = 0.15 → “muy cerca” a la línea para Regla 3 (r).
+ E = 0.12 → zona después del cruce para Reglas 5 y 6 (e).

# Fases

U_MIN_GREEN = 1.5 s aprox. → mínimo en verde (u).

YELLOW_TIME = 0.6 s → duración del amarillo.

# Umbrales

N_THRESHOLD = 16 → umbral del contador de demanda (n).

M_FEW = 2 → “pocos vehículos” para la excepción (m).

# Dinámica

TRAFFIC → intensidad global de nacimientos.

SPEED → factor global de velocidad.

CAR_LEN → longitud virtual para espaciamiento.


# Reglas auto-organizantes 

A continuación se listan tal cual las reglas:

+ Contador por eje en rojo:
En cada paso de tiempo, agregar a un contador el número de vehículos que se acercan o esperan ante una luz roja a una distancia d.
Cuando este contador exceda un umbral n, cambiar el semáforo.
(Siempre que el semáforo cambia, reiniciar el contador en cero).
→ (d = D, n = N_THRESHOLD)

+ Mínimo en verde:
Los semáforos deben permanecer un mínimo tiempo u en verde.
→ (u = U_MIN_GREEN)

+ Excepción “pocos por cruzar”:
Si pocos vehículos (m o menos, > 0) están por cruzar una luz verde a una corta distancia r, no cambiar el semáforo.
→ (m = M_FEW, r = R)

+ Dar prioridad al que tiene demanda:
Si no hay un vehículo que se acerque a una luz verde a una distancia d y al menos uno se aproxima a una luz roja a distancia d, entonces cambiar el semáforo.
→ (d = D)

+ Evitar bloquear la caja (una dirección):
Si hay un vehículo detenido en el camino a una corta distancia e más allá de una luz verde, cambiar el semáforo.
→ (e = E)

+ Evitar gridlock (ambas direcciones):
Si hay vehículos detenidos en ambas direcciones a una corta distancia e más allá de la intersección, entonces cambiar ambas luces a rojo.
Cuando una de las direcciones se libere, restaurar la luz verde en esa dirección.
→ (e = E)


# Mejoras añadidas respecto al esquema base

+ Detección de bloqueo sostenido (GL_STICK) → transición a ALL_RED.
+ Recuperación automática al liberar un eje.
+ Liberación forzada alternando ejes si ALL_RED persiste (FORCE_RELEASE).
+ Generación Poisson por carril con espaciamiento mínimo para evitar trenes pegados.
+ Controles interactivos de tráfico y velocidad.

