import os
import torch
import argparse
import torchvision  
from PIL import Image, ImageDraw, ImageFont
from torchvision.transforms import functional as F

def get_predict_box(model, device, image, threshold=0.95):
    model.eval()
    img1 = F.to_tensor(image)
    with torch.no_grad():
        prediction = model([img1.to(device)])
    
    boxes = prediction[0]['boxes']
    scores = prediction[0]['scores']
    labels = prediction[0]['labels']

    # Kana, Kanji, English, Number, Symbol
    label_map = ['Kana', 'Kanji', 'English', 'Number', 'Symbol']

    trueBoxes = []
    for index, box in enumerate(boxes):
        if scores[index] >= threshold:
            # xmin, ymin, xmax, ymax, label
            trueBoxes.append([int(box[0]), int(box[1]), int(box[2]), int(box[3]), label_map[labels[index] - 1]])
    model.train()
    return trueBoxes

def get_args():
    parser = argparse.ArgumentParser(description='Predict masks from input images',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--model', '-m', default='MODEL.pth',
                        metavar='FILE',
                        help="Specify the file in which the model is stored")
    parser.add_argument('--input', '-i', help='Filename of input images', required=True)
    parser.add_argument('--output', '-o', help='Filename of predict text region result')

    # output detected textblock if it is true
    parser.add_argument('--crop', '-c', help='Output detected jptext if it is true', dest='crop', action='store_true')
    parser.set_defaults(crop=False)

    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    device = torch.device('cuda') if torch.cuda.is_available else torch.device('cpu')
    model = torch.load(args.model, map_location=device)

    model = model.to(device=device)
    model.eval()

    img = Image.open(args.input).convert('RGB')

    # img = img.resize((1000, 2000))

    draw_img = img.copy()
    draw = ImageDraw.Draw(draw_img)
    fontSize = 3
    threshold = 0.95
    myFont = ImageFont.truetype('consola.ttf', fontSize)

    img1 = F.to_tensor(img)
    with torch.no_grad():
        prediction = model([img1.to(device)])
    
    print(prediction)

    boxes = prediction[0]['boxes']
    scores = prediction[0]['scores']
    labels = prediction[0]['labels']

    result_folder = f'.\output'
    for f in os.listdir(result_folder):
        os.remove(os.path.join(result_folder, f))

    # Kana, Kanji, English, Number, Symbol
    label_map = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]

    count = 0
    for index, box in enumerate(boxes):
        if scores[index] > threshold:
            draw.rectangle([(int(box[0]), int(box[1])), (int(box[2]), int(box[3]))], fill=None, outline=label_map[labels[index] - 1])
            # draw.text([int(box[0]), int(box[1]) - fontSize], str('{:.5f}'.format(scores[index].item())), font=myFont, fill='green')
            # draw.text([int(box[0]), int(box[1])], str(labels[index].item()), font=myFont, fill='red')
            if args.crop:
                sub_img = img.crop((int(box[0]), int(box[1]), int(box[2]), int(box[3])))
                sub_img.save(os.path.join('output', str(count) + '.jpg'))
            count += 1
            
    print(f'All Count : {count}')

    draw_img.save(args.output)