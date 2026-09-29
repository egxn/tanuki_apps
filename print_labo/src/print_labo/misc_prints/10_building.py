from tanuki.dsl import *

building_x = 60
building_y = 200
building_z = 135
watt_thick = 1.2

room_x = 30
room_y = 30
room_z = 22.5

col_x = 4.5
col_y = 5
col_z = 135


floor_z_1 = building_z/2 - room_z / 2

def new_room():
    room = cube(room_x, room_y, room_z, "room")
    h_room = cube(room_x - watt_thick*2, room_y -  watt_thick*2, room_z + 10, "room")
    room = difference(room, [h_room])

    return room

def new_bath():
    bath = cube(room_x /2, 25, room_z, "bath")
    h_bath = cube(room_x /2 - watt_thick*2, 25 - watt_thick*2, room_z + 10, "bath_h")
    bath = difference(bath, [h_bath])

    return bath

def create_building():
    with model("building") as context:
        building_perimeter = cube(building_x, building_y, 1, "building")
        col = cube(col_x, col_y, col_z, "column")


        step_x = 9
        step_y = 2.83
        step_z = 1.8
        release_x = 18
        release_y = 9
        release_z = 1.8
        ladders_y = 43 

        ladders = cube(room_x, ladders_y, room_z, "ladders")
        h_ladders = cube(room_x - watt_thick*2, ladders_y - watt_thick*2, room_z + 10, "ladders_h")
        ladders = difference(ladders, [h_ladders])
        step = cube(step_x, step_y, step_z, "step")
        release = cube(release_x, release_y, release_z, "release")

        ladders = union([
            ladders,
            release | place(0, ladders_y/2 - release_y/2  - watt_thick, 0),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 - watt_thick ,      + step_z    ),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 * 3 - watt_thick  , + step_z * 2),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 * 5 - watt_thick ,  + step_z * 3),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 * 7 - watt_thick ,  + step_z * 4),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 * 9 - watt_thick ,  + step_z * 5),
            step | place(step_x/2,  ladders_y/2 - release_y  - step_y/2 * 11 - watt_thick , + step_z * 6),
            step | place(-step_x/2,  ladders_y/2 - release_y  - step_y/2 - watt_thick ,    - step_z    ),
            step | place(-step_x/2, ladders_y/2 - release_y  - step_y/2 * 3 - watt_thick , - step_z * 2),
            step | place(-step_x/2, ladders_y/2 - release_y  - step_y/2 * 5 - watt_thick , - step_z * 3),
            step | place(-step_x/2, ladders_y/2 - release_y  - step_y/2 * 7 - watt_thick , - step_z * 4),
            step | place(-step_x/2, ladders_y/2 - release_y  - step_y/2 * 9 - watt_thick , - step_z * 5),
            step | place(-step_x/2, ladders_y/2 - release_y  - step_y/2 * 11 - watt_thick ,- step_z * 6 ),
        ])
        


        output(join([
            building_perimeter | place(0, building_y/2, -building_z/2),
            ladders | place(0, building_y - room_y*3 - 43, -floor_z_1),
            col | place(building_x / 2 - col_x/2, 50, 0),
            col | place(-(building_x / 2 - col_x/2), 50, 0),
            col | place(building_x / 2 - col_x/2, 75, 0),
            col | place(-(building_x / 2 - col_x/2), 75, 0),
            col | place(building_x / 2 - col_x/2, 123.3, 0),
            col | place(-(building_x / 2 - col_x/2), 123.3, 0),
            col | place(building_x / 2 - col_x/2, 166, 0),
            col | place(-(building_x / 2 - col_x/2), 166, 0),
            col | place(building_x / 2 - col_x/2, building_y - col_y/2, 0),
            col | place(-(building_x / 2 - col_x/2), building_y - col_y/2, 0),
        ]))

    return context.graph

def create_apt_left():
    with model("apt_left") as context:

        output(join([
            new_room() | place(building_x / 2 - room_x/2, building_y - room_y/2, -floor_z_1),
            new_room() | place(0, building_y - room_y/2 - room_y + watt_thick, -floor_z_1),
            new_bath() | place(room_x / 4,  building_y - room_y/2 - room_y*3 + watt_thick*5 , -floor_z_1),
        ]))

    return context.graph

def create_apt_right():
    with model("apt_right") as context:

        output(join([
            new_room() | place(-(building_x / 2 - room_x/2), building_y - room_y/2, -floor_z_1),
            new_room() | place(0, building_y - room_y/2 - room_y*2 + watt_thick*2, -floor_z_1),
            new_bath() | place(-room_x / 4, building_y - room_y/2 - room_y*3 + watt_thick*5 , -floor_z_1),
        ]))

    return context.graph

ALL_PARTS = [
    create_building(),
    create_apt_left(),
    create_apt_right(),
]


if __name__ == "__main__":
    from pathlib import Path

    from print_labo.utils.compile_cli import run_compile_cli


run_compile_cli(
    graphs=ALL_PARTS,
    description="Compile building",
    source_script=Path(__file__).resolve(),
    default_output="building.py",
    default_output_dir="building_out",
    watch_base_dir=Path(__file__).resolve().parent,
)
