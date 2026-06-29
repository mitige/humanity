from core.society import SocietyManager
from schemas.models import SimConfig, WorldStimulus, PerturbRequest


def test_world_stimulus_injects_into_shared_world():
    soc = SocietyManager(SimConfig(n_agents=1, n_objects=2, world_noise=0.0, random_seed=1))
    before = len(soc.world.objects)
    obj = soc.agents[0].world_stimulus(WorldStimulus(kind="hazard", intensity=3.0))
    assert obj.id in soc.world.objects and len(soc.world.objects) == before + 1
    assert obj.kind == "hazard"


def test_choc_perturb_drains_shared_body_energy():
    soc = SocietyManager(SimConfig(n_agents=1, world_noise=0.0, random_seed=1, initial_energy=100.0))
    soc.tick()
    e0 = soc.world.agents[0].energy
    soc.agents[0].perturb(PerturbRequest(type="choc", magnitude=2.0))
    assert soc.world.agents[0].energy < e0
