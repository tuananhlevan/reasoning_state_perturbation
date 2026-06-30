from client_utils import get_client, encode_image
from extract_table import extract_table_from_image
from decompose_graph import decompose_claim_to_graph
from verbalize_graph import verbalize_graph_to_claim
from verify_contradiction import verify_contradiction
from mutate_graph import mutate_claim_graph
from map_terminology import generate_terminology_mapping

def main():
    client = get_client()
    
    # 1. Encode image
    encoded_img = encode_image("pdf_page_1.jpg")
    
    # 2. Extract table data
    print("Extracting table data from image...")
    table_data = extract_table_from_image(client, encoded_img)
    print(table_data)
    print("------------------------------")
    
    faithful_reference_paragraph = "\\input{tables/diffusion_hr_main} Apart from ImageNet 512$\\times$512, we also test our models for higher-resolution image generation. As shown in Table~\\ref{tab:diffusion_hr_main}, we have a similar finding where \\modelshort-f32p1 achieves better FID than SD-VAE-f8p2 for all cases."

    # 2.5 Generate terminology mapping (Generalizable context)
    print("\nGenerating terminology mapping...")
    domain_context = generate_terminology_mapping(client, faithful_reference_paragraph, table_data)
    print("--- Dynamic Domain Context ---")
    print(domain_context)
    print("------------------------------")

    # 3. Decompose claim to graph
    print("\nDecomposing claim to graph...")
    claim_graph = decompose_claim_to_graph(client, faithful_reference_paragraph)
    print("Claim graph:", claim_graph)
    
    # 3.5 Mutate graph
    print("\nMutating claim graph to introduce contradiction...")
    mutated_claim_graph = mutate_claim_graph(client, claim_graph)
    print("Mutated claim graph:", mutated_claim_graph)
    
    # 4. Verbalize mutated graph to claim
    print("\nVerbalizing mutated graph...")
    counterfactual_claim = verbalize_graph_to_claim(client, mutated_claim_graph)
    print("Counterfactual claim:", counterfactual_claim)
    
    # 5. Verify contradiction
    print("\nVerifying contradiction...")
    is_contradiction = verify_contradiction(client, encoded_img, counterfactual_claim, domain_context, table_data)
    print("Is contradiction:", is_contradiction)

if __name__ == "__main__":
    main()
