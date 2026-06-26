from model import Ollama, Provider
from DYNAMO import DYNAMO
def main():

    test=Provider("google/gemma-4-e2b", "OpenAI", "lm-studio", "http://localhost:1234/v1")
    v1=DYNAMO(test, 2, """Create a basic Minecraft-style voxel game in a single HTML file with:

- First-person 3D view with WASD movement and mouse look
- Simple terrain generation (grass, dirt, stone blocks)
- Ability to place and break blocks with mouse clicks
- A 16x16x16 block world

Use Three.js via CDN for 3D rendering.""")
    v1.run()


    

    


if __name__ == "__main__":
    main()
