import FreeCAD as App
import FreeCADGui  # Used only in GUI mode
import Part
import math
import traceback


MODEL_NAME = "HoneycombWithFrame"
HONEYCOMB_NAME = "Honeycomb"
FRAME_NAME = "Frame"


class HexagonCell:
    """
    Represents a single hexagon cell with a hollow center.
    """

    def __init__(self, center, outer_radius, wall_thickness, extrusion_height):
        """
        Initializes the hexagon cell.

        Parameters:
            center (App.Vector): Center point of the hexagon.
            outer_radius (float): Radius of the outer hexagon.
            wall_thickness (float): Thickness of the cell wall.
            extrusion_height (float): Height to extrude the 2D shape into 3D.
        """
        self.center = center
        self.outer_radius = outer_radius
        self.wall_thickness = wall_thickness
        self.extrusion_height = extrusion_height

    def create_shape(self):
        """
        Creates a 3D hollow hexagon shape by subtracting an inner hexagon
        from an outer hexagon and then extruding the result.

        Returns:
            Part.Shape: The extruded hexagon shape.
        """
        points_outer = []
        points_inner = []
        inner_radius = self.outer_radius - self.wall_thickness

        # Generate vertices for the outer and inner hexagon
        for i in range(6):
            angle = math.radians(60 * i - 30)
            # Outer vertex
            px_outer = self.center.x + self.outer_radius * math.cos(angle)
            py_outer = self.center.y + self.outer_radius * math.sin(angle)
            points_outer.append(App.Vector(px_outer, py_outer, 0))
            # Inner vertex
            px_inner = self.center.x + inner_radius * math.cos(angle)
            py_inner = self.center.y + inner_radius * math.sin(angle)
            points_inner.append(App.Vector(px_inner, py_inner, 0))

        # Close the polygons by appending the first point at the end
        points_outer.append(points_outer[0])
        points_inner.append(points_inner[0])

        try:
            outer_wire = Part.makePolygon(points_outer)
            inner_wire = Part.makePolygon(points_inner)
            outer_face = Part.Face(outer_wire)
            inner_face = Part.Face(inner_wire)
        except Exception as e:
            App.Console.PrintError(f"Error while creating hexagon wires/faces: {e}\n")
            traceback.print_exc()
            raise e

        # Subtract the inner face from the outer face and extrude the result
        hexagon_face = outer_face.cut(inner_face)
        return hexagon_face.extrude(App.Vector(0, 0, self.extrusion_height))


class HoneycombGenerator:
    """
    Generates a honeycomb structure composed of multiple hexagon cells.
    """

    def __init__(self, width, length, cell_size, wall_thickness, extrusion_height, x_offset=0, y_offset=0):
        """
        Initializes the honeycomb generator.

        Parameters:
            width (float): Total width of the grid area.
            length (float): Total length of the grid area.
            cell_size (float): Diameter of the hexagon cell (defines outer_radius).
            wall_thickness (float): Thickness of each cell wall.
            extrusion_height (float): Height to extrude each hexagon.
            x_offset (float): Optional X offset for the grid start.
            y_offset (float): Optional Y offset for the grid start.
        """
        self.width = width
        self.length = length
        self.cell_size = cell_size
        self.wall_thickness = wall_thickness
        self.extrusion_height = extrusion_height
        self.x_offset = x_offset
        self.y_offset = y_offset

        # Calculate derived hexagon parameters
        self.outer_radius = cell_size / 2.0
        self.hex_height = self.outer_radius * 2.0  # Vertical span of the hexagon
        self.hex_width = math.sqrt(3) * self.outer_radius  # Horizontal width of the hexagon
        self.row_spacing = self.hex_height * 0.75  # Vertical spacing with overlap
        self.col_spacing = self.hex_width  # Horizontal spacing

    def generate_honeycomb(self):
        """
        Generates the honeycomb structure by arranging hexagon cells in a grid pattern.

        Returns:
            tuple: (combined_honeycomb (Part.Shape), num_rows (int), num_cols (int))
        """
        hexagons = []
        num_rows = int(math.floor(self.length / self.row_spacing))
        num_cols = int(math.floor(self.width / self.col_spacing))
        App.Console.PrintMessage(f"Generating honeycomb: {num_rows} rows, {num_cols} columns\n")

        for row in range(num_rows):
            for col in range(num_cols):
                # Compute the center for each hexagon cell
                x = self.x_offset + col * self.col_spacing
                y = self.y_offset + row * self.row_spacing
                # Offset alternate rows for the honeycomb pattern
                if row % 2 == 1:
                    x += self.col_spacing / 2.0

                # Ensure the hexagon fits within the defined boundaries
                if (x + self.hex_width / 2.0 <= self.width) and (y + self.hex_height / 2.0 <= self.length):
                    cell_center = App.Vector(x, y, 0)
                    cell = HexagonCell(cell_center, self.outer_radius, self.wall_thickness, self.extrusion_height)
                    try:
                        shape = cell.create_shape()
                        hexagons.append(shape)
                    except Exception as e:
                        App.Console.PrintError(f"Error creating hexagon at row {row}, col {col}: {e}\n")
                        traceback.print_exc()

        if not hexagons:
            App.Console.PrintError("No hexagon cells were generated. Check your parameters.\n")
            return None, num_rows, num_cols

        # Fuse all hexagon shapes into a single compound shape
        combined_shape = hexagons[0]
        for shape in hexagons[1:]:
            combined_shape = combined_shape.fuse(shape)

        return combined_shape, num_rows, num_cols


class FrameGenerator:
    """
    Generates a frame that exactly encloses a given honeycomb structure.
    """

    def __init__(self, x_min, x_max, y_min, y_max, frame_thickness, extrusion_height):
        """
        Initializes the frame generator.

        Parameters:
            x_min (float): Minimum X coordinate of the honeycomb.
            x_max (float): Maximum X coordinate of the honeycomb.
            y_min (float): Minimum Y coordinate of the honeycomb.
            y_max (float): Maximum Y coordinate of the honeycomb.
            frame_thickness (float): Thickness (offset) of the frame.
            extrusion_height (float): Height to extrude the frame (should match honeycomb extrusion).
        """
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.frame_thickness = frame_thickness
        self.extrusion_height = extrusion_height

    def create_frame(self):
        """
        Creates a 3D frame that encloses the honeycomb structure.

        Returns:
            Part.Shape: The extruded frame shape.
        """
        # Define the outer rectangle (expanded by frame_thickness)
        outer_points = [
            App.Vector(self.x_min - self.frame_thickness, self.y_min - self.frame_thickness, 0),
            App.Vector(self.x_max + self.frame_thickness, self.y_min - self.frame_thickness, 0),
            App.Vector(self.x_max + self.frame_thickness, self.y_max + self.frame_thickness, 0),
            App.Vector(self.x_min - self.frame_thickness, self.y_max + self.frame_thickness, 0),
            App.Vector(self.x_min - self.frame_thickness, self.y_min - self.frame_thickness, 0)
        ]
        # Define the inner rectangle (matching the honeycomb boundaries)
        inner_points = [
            App.Vector(self.x_min, self.y_min, 0),
            App.Vector(self.x_max, self.y_min, 0),
            App.Vector(self.x_max, self.y_max, 0),
            App.Vector(self.x_min, self.y_max, 0),
            App.Vector(self.x_min, self.y_min, 0)
        ]

        try:
            outer_wire = Part.makePolygon(outer_points)
            inner_wire = Part.makePolygon(inner_points)
            outer_face = Part.Face(outer_wire)
            inner_face = Part.Face(inner_wire)
        except Exception as e:
            App.Console.PrintError("Error while creating frame wires/faces: " + str(e) + "\n")
            traceback.print_exc()
            raise e

        # Subtract the inner face from the outer face to create the frame profile
        frame_profile = outer_face.cut(inner_face)
        # Extrude the profile to generate the 3D frame
        return frame_profile.extrude(App.Vector(0, 0, self.extrusion_height))


def main():
    """
    Main function to generate the honeycomb structure with an exact-fit frame.
    """
    # Define parameters (these can be exposed via a UI or config file)
    width = 70.0  # Overall grid width (mm)
    length = 60.0  # Overall grid length (mm)
    wall_thickness = 1.0  # Thickness of each hexagon wall (mm)
    cell_size = 10.0  # Hexagon cell size (defines outer diameter, mm)
    extrusion_height = 2.5  # Height to extrude each hexagon (mm)
    frame_thickness = 2.0  # Thickness (offset) of the frame (mm)

    # Create a new FreeCAD document
    doc = App.newDocument(MODEL_NAME)

    # Generate the honeycomb structure using the HoneycombGenerator class
    honeycomb_generator = HoneycombGenerator(width, length, cell_size, wall_thickness, extrusion_height)
    honeycomb_shape, num_rows, num_cols = honeycomb_generator.generate_honeycomb()
    if honeycomb_shape is None:
        App.Console.PrintError("Failed to generate the honeycomb structure.\n")
        return

    App.Console.PrintMessage(f"Honeycomb generated with {num_rows} rows and {num_cols} columns.\n")
    honeycomb_obj = doc.addObject("Part::Feature", HONEYCOMB_NAME)
    honeycomb_obj.Shape = honeycomb_shape

    # Retrieve the bounding box of the honeycomb for frame creation
    bounds = honeycomb_shape.BoundBox
    x_min, x_max = bounds.XMin + frame_thickness, bounds.XMax - frame_thickness
    y_min, y_max = bounds.YMin + frame_thickness, bounds.YMax - frame_thickness
    App.Console.PrintMessage(f"Honeycomb bounds: X=({x_min:.2f}, {x_max:.2f}), Y=({y_min:.2f}, {y_max:.2f})\n")

    # Generate the frame using the FrameGenerator class
    frame_generator = FrameGenerator(x_min, x_max, y_min, y_max, frame_thickness, extrusion_height)
    frame_shape = frame_generator.create_frame()
    frame_obj = doc.addObject("Part::Feature", FRAME_NAME)
    frame_obj.Shape = frame_shape

    # Recompute the document to update the model
    doc.recompute()

    # Fit the view if running in GUI mode
    if hasattr(App, "Gui"):
        try:
            FreeCADGui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass


if __name__ == "__main__":
    main()
