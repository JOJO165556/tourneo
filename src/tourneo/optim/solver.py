import math
import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from tourneo.optim.evaluation import evaluer_tournee, SERVICE_MIN

HORIZON_MIN = 2880
PENALITE_NON_LIVREE = 100000


def resoudre(inst, vehicules, temps_limite_s=20, penalite_retard=200, routes_initiales=None):
    n = len(inst["demande"])
    nb_vehicules = len(vehicules)
    manager = pywrapcp.RoutingIndexManager(n, nb_vehicules, 0)
    routing = pywrapcp.RoutingModel(manager)

    for k, v in enumerate(vehicules.itertuples()):
        couts = np.rint(inst["distance"] * float(v.cout_km)).astype(int)
        indice = routing.RegisterTransitCallback(
            lambda i, j, c=couts: int(c[manager.IndexToNode(i)][manager.IndexToNode(j)])
        )
        routing.SetArcCostEvaluatorOfVehicle(indice, k)

    demande = [math.ceil(x) for x in inst["demande"]]
    indice_demande = routing.RegisterUnaryTransitCallback(lambda i: demande[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(
        indice_demande, 0, [math.floor(c) for c in vehicules["capacite_kg"]], True, "Capacite"
    )

    duree = np.rint(inst["duree"]).astype(int)

    def temps(i, j):
        a = manager.IndexToNode(i)
        b = manager.IndexToNode(j)
        return int(duree[a][b]) + (SERVICE_MIN if a != 0 else 0)

    indice_temps = routing.RegisterTransitCallback(temps)
    routing.AddDimension(indice_temps, HORIZON_MIN, HORIZON_MIN, False, "Temps")
    dimension = routing.GetDimensionOrDie("Temps")
    depart = int(inst["heure_debut_min"])
    for k in range(nb_vehicules):
        dimension.CumulVar(routing.Start(k)).SetRange(depart, depart)
    for noeud in range(1, n):
        indice = manager.NodeToIndex(noeud)
        dimension.CumulVar(indice).SetMin(int(inst["debut"][noeud]))
        dimension.SetCumulVarSoftUpperBound(indice, int(inst["fin"][noeud]), penalite_retard)
        routing.AddDisjunction([indice], PENALITE_NON_LIVREE)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.TABU_SEARCH
    params.time_limit.seconds = int(temps_limite_s)
    routing.CloseModelWithParameters(params)
    solution = None
    if routes_initiales:
        routes = []
        for v in vehicules.itertuples():
            noeuds = routes_initiales.get(int(v.id_vehicule), [])
            routes.append([manager.NodeToIndex(x) for x in noeuds if 0 < x < n])
        initiale = routing.ReadAssignmentFromRoutes(routes, True)
        if initiale is not None:
            solution = routing.SolveFromAssignmentWithParameters(initiale, params)
    if solution is None:
        solution = routing.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError("Aucune solution trouvée")
    tournees = []
    livrees = set()
    for k, v in enumerate(vehicules.itertuples()):
        indice = routing.Start(k)
        arrets = []
        while not routing.IsEnd(indice):
            noeud = manager.IndexToNode(indice)
            if noeud != 0:
                arrets.append(noeud)
            indice = solution.Value(routing.NextVar(indice))
        livrees.update(arrets)
        tournee = evaluer_tournee(inst, arrets, float(v.cout_km))
        tournee["id_vehicule"] = int(v.id_vehicule)
        tournees.append(tournee)
    non_livrees = sorted(set(range(1, n)) - livrees)
    return tournees, non_livrees