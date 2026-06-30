from pdf2image import convert_from_path

images = convert_from_path('test/ref/tab_diffusion_ablation_vae_patchsize.pdf', dpi=300)
image_path = 'pdf_page_1.jpg'
images[0].save(image_path, 'JPEG')