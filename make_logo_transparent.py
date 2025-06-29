from PIL import Image

# Path to your current logo
input_path = "app/static/lion_logo.png/lion_logo.png"
output_path = "app/static/lion_logo.png/lion_logo_transparent.png"

# Open the image
img = Image.open(input_path).convert("RGBA")
datas = img.getdata()

newData = []
for item in datas:
    # If the pixel is white (or nearly white), make it transparent
    if item[0] > 240 and item[1] > 240 and item[2] > 240:
        newData.append((255, 255, 255, 0))
    else:
        newData.append(item)

img.putdata(newData)
img.save(output_path)
print(f"Saved transparent logo to {output_path}") 