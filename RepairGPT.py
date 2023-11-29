import subprocess
import sys
import re
from openai import OpenAI

# ChatGPT Functions
def getKey():
    file_path = 'secretkey.txt'
    with open(file_path, 'r') as file:
        file_contents = file.read()
    return file_contents

def generate_prompt(code, err_type):
    return f'patch and return the code to improve it\'s quality and correctness, it currently has a {err_type} error, don\'t include explanations in your responses\n{code}' 

# Helper Functions
def generateString(i):
    return 'a' * i

def read_file_to_string(file_path):
    try:
        with open(file_path, 'r') as file:
            file_contents = file.read()
            return file_contents
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def write_string_to_file(file_path, content):
    write_path = f'{c_file_path[:-2]}_patch.c'
    try:
        with open(write_path, 'w') as file:
            file.write(content)
        print(f'Successfully wrote content to {write_path}')
    except Exception as e:
        print(f'Error writing to {write_path}: {e}')

# Address Sanitizer Functions
def identifyError(c_file_path, arg2=None):
    try:
        # Compile and run the C file with Address Sanitizer
        result_output = compile_and_run_with_asan(c_file_path, arg2)
        if (result_output != None):
            return result_output.split()[3]
        else:
            print("No errors found")
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
    return None

def compile_and_run_with_asan(c_file_path, arg2=None):
    # Compile the C file with Address Sanitizer
    compile_command = f"gcc -fsanitize=address -o {c_file_path[:-2]}_asan {c_file_path}"
    subprocess.run(compile_command, shell=True, check=True)

    if (arg2 != None):
        for i in range(1, int(arg2)):
            input_data = generateString(i)
            run_command = f"./{c_file_path[:-2]}_asan {input_data}"
            result = subprocess.run(run_command, shell=True, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if ("==ERROR:" in (result.stdout + result.stderr)):
                return result.stdout + result.stderr
        return None
    else:
        run_command = f"./{c_file_path[:-2]}_asan"
        result = subprocess.run(run_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    return result.stdout + result.stderr

if __name__ == "__main__":
    # Check if a C file path is provided as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_c_file>")
        sys.exit(1)

    c_file_path = sys.argv[1]

    arg2 = None
    if len(sys.argv) == 3:
        arg2 = sys.argv[2]
    
    err_type = identifyError(c_file_path, arg2)

    if (err_type):
        code = read_file_to_string(c_file_path)
        prompt = generate_prompt(code, err_type)
        
        # ChatGPT Code
        client = OpenAI(
            api_key=getKey(),
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        patch = (response.choices[0].message.content)
        print(patch)
        write_string_to_file(c_file_path, patch)
        
    else: 
        sys.exit(1)