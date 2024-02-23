import subprocess
import sys
import json
import os
import re
import argparse
import regex
from dotenv import load_dotenv
from openai import OpenAI
from subprocess import Popen, PIPE



def build_program(file_path, shell):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    for line in lines:
        command = line.strip()
        # Send the command to the shell
        shell.stdin.write((command + '\n').encode())
        shell.stdin.flush()



def run_program(file_path, shell):
    with open(file_path, 'r') as file:
        command = file.readline().strip()

    # Send the command to the shell
    shell.stdin.write((command + '\n').encode())
    shell.stdin.flush()

    stdout, stderr = shell.communicate()

    # Close the shell after all commands have been sent
    shell.stdin.close()
    shell.wait()

    if stderr:
        return True, stderr.decode()
    else:
        return False, ''
    

    


# given a filename and a starting point search path, this function will search for the file and return the relative path to it
def find_file(filename, search_path):

    for root, dir, files in os.walk(search_path):
        if filename in files:
            return os.path.relpath(os.path.join(root, filename), search_path)
        
    return None



# this function, given a file path and a function name, will return the code of the function
def get_function_code(file_path, function_name):
    print(f"Searching for function {function_name} in file {file_path}")
    with open(file_path, 'r') as file:
        lines = file.readlines()

        function_code = ""
        opening_round_brace = False
        closing_round_brace = False
        opening_curly_brace = False
        bracket_counter = 0
        function_starting_line = 0
        function_ending_line = 0
        index = 0

        for line in lines:
            index += 1
            if function_name in line and line.count('(') == 1 and not ';' in line:
                if line.index(function_name) < line.index('('):
                    function_starting_line = index
                    opening_round_brace = True
                    function_code += line
                
            if opening_round_brace and not closing_round_brace and not opening_curly_brace:
                if ')' in line:
                    closing_round_brace = True
                    function_code += line
                if ';' in line:
                    closing_round_brace = False
                    opening_round_brace = False
                    function_code = ""
            
            if opening_round_brace and closing_round_brace and not opening_curly_brace:
                function_code += line
                if '{' in line:
                    opening_curly_brace = True
                elif ';' in line:
                    closing_round_brace = False
                    opening_round_brace = False
                    function_code = ""
            
            if opening_curly_brace:
                function_code += line
                if '{' in line:
                    bracket_counter += line.count('{')
                if '}' in line:
                    bracket_counter -= line.count('}')
                    if bracket_counter == 0:
                        function_ending_line = index
                        return function_starting_line, function_ending_line, function_code
                    
    return None, None, None
               



# creates and sends the request to OpenAI - just an example for now
# returns the response from OpenAI
# the reponse should contain a json file containing a list of items
# each item should contain the file name, function name and line number
def ask_llm_to_find(report):
    completion =  client.chat.completions.create(

        messages=[
            {
                "role": "user",
                "content": report + """Given this information in which files and functions should i look into to locate the bug? Return the results in a json format structured like the following example, without any additional comments.
                [{
                    "file": "example1.py",
                    "function": "function1"
                }]""",
            }
        ],

        model="gpt-3.5-turbo",
    )
    
    #if completion.choices[0].message.content starts with ``` then we want to discard the first and last line
    if completion.choices[0].message.content.startswith("```"):
        return completion.choices[0].message.content.split('\n')[1:-1]

    return completion.choices[0].message.content


# creates and sends the request to OpenAI - just an example for now
# returns the response from OpenAI
# the reponse should contain the fixed code
def ask_llm_to_fix(report, function_code):
    completion =  client.chat.completions.create(

        messages=[
            {
                "role": "user",
                "content": f"{report}\n{function_code}\n Given this information, provide a fix for the function without changing the function prototype. Return just the code for the function in its entirety without any additional comments",
            }
        ],

        model="gpt-3.5-turbo",
    )
    print("\n\nResponse from OpenAI")
    print(completion.choices[0].message.content)
    print("\n\n")

    #if completion.choices[0].message.content starts with ``` then we want to discard the first and last line
    if completion.choices[0].message.content.startswith("```"):
        return completion.choices[0].message.content.split('\n')[1:-1]

    return completion.choices[0].message.content


def replace_function_in_c_file(filepath, new_function_code, starting_line, ending_line):
    with open(filepath, 'r') as file:
        lines = file.readlines()

    # Split the new function code into lines, adding the newline characters back
    new_lines = [line + '\n' for line in new_function_code.split('\n')]

    # Replace the lines with the new function code
    lines[starting_line-1:ending_line] = new_lines

    with open(filepath, 'w') as file:
        file.writelines(lines)

def parse_arguments():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("-b", default="build.txt", type=str)
    parser.add_argument("-c", default="run.txt", type=str)
    parser.add_argument("-n", default=1, type=int)
    parser.add_argument("-r", default=None, type=str)
    args = parser.parse_args()

    return args.b, args.c, int(args.n), args.r

if __name__ == '__main__':
    # load .env file that contains the OpenAI API key
    load_dotenv()

    build_commands, run_commands, max_number_of_tries, report = parse_arguments()
    print(build_commands, run_commands, max_number_of_tries, report)


    # Start a shell
    shell = Popen(['/bin/bash'], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    build_program(build_commands, shell)

    crash, stderr_content = run_program(run_commands, shell)
    
    # set up the OpenAI thing - set max retries to 0 for debugging - raise for production TODO
    client = OpenAI( max_retries=0)

    try_count = 0

    while crash and try_count < max_number_of_tries:
        try_count += 1
        print(stderr_content)
        if report is not None:
            with open(report, 'r') as file:
                stderr_content = file.read()


        print(f"\n\n{stderr_content}")
   
        file_to_check_json = ask_llm_to_find(stderr_content)

        print(f"\n\n{file_to_check_json}")

        json_data = json.loads(file_to_check_json)

        result = []
        for item in json_data:
            result.append({
                'file': item['file'],
                'function': item['function']
            })

        print(f"\n\n{result}")


        print("\n\n")
        # for each item returned we search for the file and retrieve the indicated function code
        fixed_function_code = None
        function_code = None
        for item in result:
            file_path = find_file(item['file'], '.')
            if file_path is not None:
                print(f"File found at {file_path}")
                if item['function'] == "readSeparateTilesIntoBuffer": #TODO this was done just to test and not hit openai rate limiter
                    starting_line, ending_line, function_code = get_function_code(file_path, item['function'])
                    print(f"Function code: {function_code}")
                    print(f"Function starting line: {starting_line}")
                    print(f"Function ending line: {ending_line}")
                    if starting_line is not None:
                        print("starting line is NOT None")
                        fixed_function_code = ask_llm_to_fix(stderr_content, function_code)
                        print(f"fixed code for {item['function']}:\n{fixed_function_code}")
                    if fixed_function_code is not None and fixed_function_code != "None":
                        print("fixed function code is NOT None")
                        replace_function_in_c_file(file_path, fixed_function_code, starting_line, ending_line)
                        print(f"Function {item['function']} replaced in file {file_path}")
                        shell = Popen(['/bin/bash'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
                        build_program(build_commands, shell)
                        print("Program rebuilt")
                        crash, stderr_content = run_program(run_commands, shell)
                        if not crash:
                            print("Program ran successfully after the fix")
                            break
                        else:
                            print("Program still crashes after the fix")
                            print(stderr_content)
                            

            else:
                print(f"File {item['file']} not found")
            print("\n\n")


# # Close the shell after all commands have been sent
# shell.stdin.close()
# shell.wait()

        
