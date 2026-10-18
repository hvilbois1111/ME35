import numpy as np
import matplotlib.pyplot as plt

# Define a point
point = np.array([2, 3, 1]) # this is a point at (2,3)


# we are translating this by (1,7)
translation_x = 1
translation_y = 7


# Create a rotation matrix for 45 degrees (pi/4 radians)
theta = np.pi/4
rotation_matrix = np.array([
    [np.cos(theta), -np.sin(theta), translation_x],
    [np.sin(theta), np.cos(theta), translation_y],
    [0,0,1]
])


# Apply the rotation
rotated_point = rotation_matrix @ point #@ is matrix multiplication

print(f"Original point: {point}")
print(f"Rotated point: {rotated_point}")

# Visualization
plt.figure(figsize=(5, 5))
plt.grid(True)
plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
plt.axvline(x=0, color='k', linestyle='-', alpha=0.3)
plt.arrow(0, 0, point[0], point[1], head_width=0.1, head_length=0.1, fc='blue', ec='blue')
plt.arrow(0, 0, rotated_point[0], rotated_point[1], head_width=0.1, head_length=0.1, fc='red', ec='red')
plt.text(point[0], point[1], 'Original')
plt.text(rotated_point[0], rotated_point[1], 'Transformed')
plt.axis('equal')
plt.xlim(-20, 20)
plt.ylim(-20, 20)
plt.title('2D Transformation Example')
plt.show()

