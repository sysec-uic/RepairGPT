import os, shutil, signal, time, argparse, threading, json, re
from queue import Queue
from subprocess import Popen, PIPE
from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------------- #
#
# HOW TO - a readme might be provided with more informations
# the program should be run specifying 4 command line args
# 1) -p: the path of the target application - where the
#       executable is contained.
# 2) -b: the path to a file containing the instructions to
#       build the target, one per line.
# 3) -r: the path to a file containing the instructions to run
#       the target without the fuzzer, in the instructions
#       a placeholder called INPUT must be included where
#       the input filename should be passed.
#       e.g. ./xml_harness file.xml --> ./xml_harness INPUT
# 4) -f: the path to a file with the instructions to run the
#       fuzzer targeting the application in question.
#
# --------------------------------------------------------- #

TMP_FOLDER_ABS = "~/workshop/tmp"

##
 # This function parses the arguments provided by the user using the argparse library.
##
def parse_arguments():
    help = "AFL loop script\n -p: the path of the target application - where the executable is contained.\n  -b: the path to a file containing the instructions to build the target, one per line.\n  -r: the path to a file containing the instructions to run the target without the fuzzer, in the instructions a placeholder called INPUT must be included where the input filename should be passed.\n  e.g. ./xml_harness file.xml --> ./xml_harness INPUT\n  -f: the path to a file with the instructions to run the fuzzer targeting the application in question."


    parser = argparse.ArgumentParser(add_help=True, description=help)

    parser.add_argument("-p", default=".", type=str)
    parser.add_argument("-b", default="build.txt", type=str)
    parser.add_argument("-r", default="run.txt", type=str)
    parser.add_argument("-f", default="fuzz.txt", type=str)
    args = parser.parse_args()

    print(f"path: ./{args.p}, \nbuild_instr: {args.b}, \nrun_instr: {args.r}, \nfuzz_instr: {args.f}")
    return args.p, args.b, args.r, args.f
# --------------------------------------------------------- #



##
 # This function builds the program following the instructions provided in the file.
 # To do that, it opens a shell, changes directory to the target directory
 # writes the provided commands to the shell's stdin, executes them and waits for them to finish.
##
def build_program(path, file_path):
    print("building the target...", end='')
    shell = Popen(['/bin/bash'], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    #move into the target directory
    command = f"cd ./{path}"
    shell.stdin.write((command + '\n').encode())
    shell.stdin.flush()

    with open(f"{path}/{file_path}", 'r') as file:
        lines = file.readlines()
    
    for line in lines:
        command = line.strip()

        # Send the command to the shell
        shell.stdin.write((command + '\n').encode())
        shell.stdin.flush()

    # Wait for the command to finish
    stdout, stderr = shell.communicate()
    print(" - target compiled") 
    #print(stdout.decode())
# --------------------------------------------------------- #



##
 # This function starts the fuzzer with the target application following the instructions provided.
##   
def fuzz_program(path, file_path, event, absolute_tmp_path):
    print("starting fuzzer...", end='')
    shell = Popen(['/bin/bash'], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    #move into the target directory
    shell.stdin.write((f"cd ./{path}\n").encode())
    shell.stdin.flush()
    with open(f"{path}/{file_path}", 'r') as file:
        command = file.readline().strip()

    # Send the command to the shell
    shell.stdin.write((f"{command} & echo $! > {absolute_tmp_path}/process.pid" + '\n').encode())
    shell.stdin.flush()
    event.set() # signal the main thread that we are starting the fuzzer

    stdout, stderr = shell.communicate()
# --------------------------------------------------------- #



##
 # This function runs the target application following the instructions provided,
 # its purpose is to run the application without the fuzzer with the bug-triggering input.
 # To do this, we need to fetch the user-provided instructions and substitute the placeholder "INPUT"
 # with the filename of the bug-inducing input. Then, the function returns the content of stderr
##
def run_program(path, file_path, faulty_input_filename):
    shell = Popen(['/bin/bash'], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    #move into the target directory
    command = f"cd ./{path}"
    shell.stdin.write((command + '\n').encode())
    shell.stdin.flush()

    with open(f"{path}/{file_path}", 'r') as file:
        command = file.readline().strip()
    
    command = command.replace("INPUT", faulty_input_filename)
    print(f"running: {command}")

    # Send the command to the shell
    shell.stdin.write((command + '\n').encode())
    shell.stdin.flush()

    stdout, stderr = shell.communicate()

    if stderr:
        print("the target is crashing")
        return True, stderr.decode('utf-8', errors='ignore')
    else:
        print("the target is not crashing")
        return False, ''
# --------------------------------------------------------- #



##
 # This function monitors the folder containing the output (the bug-inducing inputs) of the fuzzer.
 # The fuzzer will add a new file everytime the target application crashes, therefore we monitor the
 # folder to detect when and with which input the target application crashes. Once a new file(s) is
 # added we stop the fuzzer and return the filename of one of them.
##
def monitor_folder(path, queue, stop_event):
    files_set = set(os.listdir(path))

    while not stop_event.is_set():
        new_files_set = set(os.listdir(path))
        if new_files_set != files_set:
            added_files = new_files_set - files_set
            if added_files and (len(added_files) > 1 or "README.txt" not in added_files):
                print(f"New files added: {', '.join(added_files)}")
                added_files.discard("README.txt")
                for item in added_files:
                    queue.put(item)
            files_set = new_files_set

        time.sleep(1)  # wait for 1 second
# --------------------------------------------------------- #



##
 # creates and sends the request to OpenAI - just an example for now
 # returns the response from OpenAI
 # the reponse should contain a json file containing a list of items
 # each item should contain the file name, function name and line number
##            
def ask_llm_to_find(report, client, logs_folder_name):
    print("we ask the LLM to find the file and functions responsible for the bug")
    completion =  client.chat.completions.create(

        messages=[
            {
                "role": "user",
                "content": report + """Given this information in which files and functions should i look into to locate the bug? Return the results in a json format structured like the following example, without any additional comments.
                [{
                    "file": "example1.py",
                    "function": "function1"
                    "line": 10
                }]""",
            }
        ],

        model="gpt-3.5-turbo",
    )


    with open(f"{logs_folder_name}/log_llm.txt", 'a') as file:
        file.write("ask_llm_to_find\n")
        file.write(f"report:\n{report}\n\n")
        file.write(f"Response from OpenAI\n{completion.choices[0].message.content}\n\n\n\n")

    #if completion.choices[0].message.content starts with ``` then we want to discard the first and last line
    if completion.choices[0].message.content.startswith("```"):
        return '\n'.join(completion.choices[0].message.content.split('\n')[1:-1]) #we return a string
    
    return completion.choices[0].message.content
# --------------------------------------------------------- #



##
 # creates and sends the request to OpenAI - just an example for now
 # returns the response from OpenAI
 # the reponse should contain the fixed code
##
def ask_llm_to_fix(report, function_code, logs_folder_name):
    completion =  client.chat.completions.create(

        messages=[
            {
                "role": "user",
                "content": f"{report}\n{function_code}\n Given this information, provide a fix. Return the fixed code for the whole function without any additional comments.",
            }
        ],

        model="gpt-3.5-turbo",
    )
    print("Response from OpenAI")
    # print(completion.choices[0].message.content)
    # print("\n\n")

    with open(f"{logs_folder_name}/log_llm.txt", 'a') as file:
        file.write("ask_llm_to_fix\n")
        file.write(f"function code:\n{function_code}\n\n")
        file.write(f"Response from OpenAI\n{completion.choices[0].message.content}\n\n\n\n")

    #if completion.choices[0].message.content starts with ``` then we want to discard the first and last line
    if completion.choices[0].message.content.startswith("```"):
        return '\n'.join(completion.choices[0].message.content.split('\n')[1:-1])

    return completion.choices[0].message.content
# --------------------------------------------------------- #



# given a filename and a starting point search path, this function will search for the file and return the relative path to it
def find_file(filename, search_path):

    for root, dir, files in os.walk(search_path):
        if filename in files:
            print(f"{search_path}/{os.path.relpath(os.path.join(root, filename), search_path)}")
            return f"{search_path}/{os.path.relpath(os.path.join(root, filename), search_path)}"
        
    return None
# --------------------------------------------------------- #



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
            read_line = False
            index += 1
            if function_name in line and line.count('(') == 1 and not ';' in line:
                if line.index(function_name) < line.index('('):
                    #function_starting_line = index
                    opening_round_brace = True
                    if not read_line:
                        function_code += line
                        read_line = True
                
            if opening_round_brace and not closing_round_brace and not opening_curly_brace:
                if ')' in line:
                    closing_round_brace = True
                if ';' in line:
                    closing_round_brace = False
                    opening_round_brace = False
                    function_code = ""
                else:
                    if not read_line:
                        function_code += line
                        read_line = True
            
            if opening_round_brace and closing_round_brace and not opening_curly_brace:
                if '{' in line:
                    opening_curly_brace = True
                    #function_code += line
                    function_starting_line = index + 1 #we want the line after the opening curly brace
                elif ';' in line:
                    closing_round_brace = False
                    opening_round_brace = False
                    function_code = ""
                else:
                    if not read_line:
                        function_code += line
                        read_line = True
            
            if opening_curly_brace:
                if not read_line:
                    function_code += line
                    read_line = True
                if '{' in line:
                    bracket_counter += line.count('{')
                if '}' in line:
                    bracket_counter -= line.count('}')
                    if bracket_counter == 0:
                        function_ending_line = index
                        return function_starting_line, function_ending_line, function_code
                    
    return None, None, None
# --------------------------------------------------------- #



def process_new_function_code(function_code: str, function_name: str) -> str:
    lines = function_code.split('\n')
    if function_name in lines[0]:
        opening_brace_index = function_code.find('{')
        if opening_brace_index != -1:
            #print("Opening brace found")
            return function_code[opening_brace_index + 1 :]
    return function_code
# --------------------------------------------------------- #



def replace_function_in_c_file(filepath: str, function_name: str, new_function_code: str, starting_line: int, ending_line: int) -> None:
    with open(filepath, 'r') as file:
        lines = file.readlines()

    new_function_code = process_new_function_code(new_function_code, function_name)

    # Split the new function code into lines, adding the newline characters back
    new_lines = [line + '\n' for line in new_function_code.split('\n')]

    # Replace the lines with the new function code
    lines[starting_line - 1 : ending_line] = new_lines

    with open(filepath, 'w') as file:
        file.writelines(lines)
# --------------------------------------------------------- #



def check_fuzzer_launch(event, thread, logs_folder_name):
    event.wait()
    time.sleep(0.1)

    if not thread.is_alive():
        with open(f"{logs_folder_name}/log.txt", 'a') as file:
            file.write(f"fuzzer has failed to start, exiting @ {time.ctime()}\n\n\n")
        print(" - fuzzer has failed to start.")
        shutil.rmtree(tmp_path)
        thread.join()
        print("exiting...")
        exit(1)
    else:
        print(" - fuzzing...")

    with open(f"{tmp_path}/process.pid", 'r') as file:
        fuzzer_pid = int(file.readline().strip())
    
    return fuzzer_pid
# --------------------------------------------------------- #



def get_fuzzer_output_folder(path, fuzz_instr):
    with open(f"{path}/{fuzz_instr}", 'r') as file:
        fuzz_command = file.readline().strip()
    return fuzz_command.split()[fuzz_command.split().index('-o') + 1]
# --------------------------------------------------------- #



def parse_llm_buggy_function_response(file_to_check_json):
    json_data = json.loads(file_to_check_json)

    result = []
    for item in json_data:
        result.append({
            'file': item['file'],
            'function': item['function'],
            'line': item['line']
        })

    print(f"\nresult[]:\n{result}\n")
    return result
# --------------------------------------------------------- #



def setup_logs_folder(path):
    if not os.path.exists("logs"):
        os.mkdir("logs")

    if path.endswith('/'):
        path = path[:-1]
    path = os.path.basename(path)

    folder_id = 0
    while os.path.exists(f"logs/{path}_{folder_id}"):
        folder_id += 1

    os.mkdir(f"logs/{path}_{folder_id}")

    return f"logs/{path}_{folder_id}"
# --------------------------------------------------------- #



def set_tmp_folder_name(path, absolute_path):
    if path.endswith('/'):
        path = path[:-1]
    path = os.path.basename(path)

    return f"tmp_{path}", f"{absolute_path}_{path}"
# --------------------------------------------------------- #



def extract_info_asan_report_info(line):
    pattern = r"#0 0x[a-f0-9]+ in (?P<function>.+) (?P<file>.+):(?P<line>\d+):\d+"
    match = re.search(pattern, line)
    if match:
        return {
            'file': match.group('file'),
            'function': match.group('function'),
            'line': int(match.group('line'))
        }
    else:
        return None
# --------------------------------------------------------- #



def asan_report_parser(report):
    result = []
    line_of_equal_signs = False
    read_buggy_functions = False
    # we go through the report line by line until we find one that is only made of '='
    for i, line in enumerate(report.split('\n')):
        if line.strip() == '=' * len(line.strip()):
            # here we have excluded the part regarding the bug-triggering input
            line_of_equal_signs = True
        # we continue until we find the first line that starts with '#'
        elif line_of_equal_signs and line.startswith('#'):
            read_buggy_functions = True
            info = extract_info_asan_report_info(line)
            if info:
                result.append(info)
        elif line_of_equal_signs and read_buggy_functions:
            if line.strip(): # if the line is not empty
                #return the vector and remaining of the report
                remaining_report = '\n'.join(report.split('\n')[i:])
                return result, remaining_report
# --------------------------------------------------------- #               
               


if __name__ == "__main__":

#|_|_| beginning of setup phase |_|_|#
    #parse command line arguments
    path, build_instr, run_instr, fuzz_instr = parse_arguments()

    # set up the tmp folder
    tmp_path, tmp_folder_absolute_path = set_tmp_folder_name(path, TMP_FOLDER_ABS)
    if not os.path.exists(tmp_path):
        os.mkdir(tmp_path)

    # set up the logs folder
    logs_folder_name = setup_logs_folder(path)

    # loads the .env file that must contain a valid OpenAI API key
    load_dotenv()

    # set up the OpenAI thing - set max retries to 0 for debugging - raise for production TODO
    client = OpenAI( max_retries=0 )

    # is it the first run - if so we use the provided instructions to fuzz the program otherwise
    # we must change the provided input folder to "-" e.g. "-i input" --> "-i -"
    first_run = True
    changed_fuzz_instr = False

    # we check if the program will be compiled with ASAN
    compiled_with_asan = False
    with open(f"{path}/{build_instr}", 'r') as file:
        lines = file.readlines()
        for line in lines:
            if "asan" in line or "ASAN" in line:
                compiled_with_asan = True
                break
#|_|_| end of setup phase |_|_|#


#|_|_| start of outer loop |_|_|#
    while True:
        # we build the program following the instructions provided
        build_program(path, build_instr)
        with open(f"{logs_folder_name}/log.txt", 'a') as file:
            file.write(f"{path}\n")

        # if it is not the first run we change the input folder to "-"
        if not first_run and not changed_fuzz_instr:
            with open(f"{path}/{fuzz_instr}", 'r') as file:
                lines = file.readlines()
            fuzz_instr = fuzz_instr.replace(".txt", "_run2.txt")
            with open(f"{path}/{fuzz_instr}", 'w') as file:
                for line in lines:
                    line = re.sub(r'(-i \S+)', '-i -', line)
                    file.write(line)
            changed_fuzz_instr = True
                



        # we launch the fuzzer as specified in the provided instructions
        fuzzer_started_event = threading.Event()
        fuzzing_thread = threading.Thread(target=fuzz_program, args=(path, fuzz_instr, fuzzer_started_event, tmp_folder_absolute_path))
        fuzzing_thread.start()
        first_run = False
        
        with open(f"{logs_folder_name}/log.txt", 'a') as file:
            file.write(f"started fuzzing @ {time.ctime()}\n")


        # we create a queue where new bug-triggering input filenames will be added by the monitoring_thread
        queue = Queue()


        # after we have started fuzzing we wait for the fuzzing thread to signal us that we have indeed started fuzzing
        # we obtain AFL pid and retrieve the output folder
        # we create a new thread that will monitor the output folder for new files, it will add their filename to the queue
        fuzzer_pid = check_fuzzer_launch(fuzzer_started_event, fuzzing_thread, logs_folder_name)
        fuzzer_output_folder = get_fuzzer_output_folder(path, fuzz_instr)

        stop_monitoring_event = threading.Event()
        monitoring_thread = threading.Thread(target=monitor_folder, args=(f"{path}/{fuzzer_output_folder}/default/crashes", queue, stop_monitoring_event))
        monitoring_thread.start()


    #|_|_| start of inner loop |_|_|#
        inner_loop = True
        while inner_loop:
            # we grab a new filename from the queue, if none is available we wait for at most two hours TODO: give possiblity to config this parameter
            print("waiting for new files...")
            try:
                new_file = queue.get(block=True, timeout=7200)
                with open(f"{logs_folder_name}/log.txt", 'a') as file:
                    file.write(f"new bug-triggering input: {new_file} @ {time.ctime()}\n")
            except queue.Empty:
                print("No new files added in the last hour")
                with open(f"{logs_folder_name}/log.txt", 'a') as file:
                    file.write(f"No new files added in the last hour, exiting @ {time.ctime()}\n")
                os.kill(fuzzer_pid, signal.SIGINT)
                shutil.rmtree(tmp_path)
                fuzzing_thread.join()
                stop_monitoring_event.set()
                monitoring_thread.join()
                print("exiting...")
                exit(0)


            # then we reproduce the bug: we substitute "INPUT" in the provided instructions
            # with the faulty input identified by the fuzzer
            # we return the report fetched from stderr and if the program is actually crashing
            is_crashing, report = run_program(path, run_instr, f"./{fuzzer_output_folder}/default/crashes/{new_file}")

            if is_crashing:
                # we try to fix the program leveraging an LLM model (e.g. ChatGPT 3.5)
                # first of all if we have a generic report we use the LLM to find file, fucntion and line of possible buggy functions
                if not compiled_with_asan:
                    file_to_check_json = ask_llm_to_find(report, client, logs_folder_name) 
                    buggy_functions = parse_llm_buggy_function_response(file_to_check_json)
                # otherwise we parse the ASAN report
                else:
                    buggy_functions, report = asan_report_parser(report)
                


            it = 0
            while is_crashing and it < 10: #TODO make this a configurable parameter just like the timeout
                for item in buggy_functions:
                    file_path = find_file(item['file'], path)
                    if file_path is None:
                        with open(f"{logs_folder_name}/log.txt", 'a') as file:
                            file.write(f"Could not find the file {item['file']} @ {time.ctime()}\n")
                        continue
                    starting_line, ending_line, function_code = get_function_code(file_path, item['function'])
                    if starting_line is not None:
                        fixed_function_code = ask_llm_to_fix(report, function_code, logs_folder_name)
                        time.sleep(60) #TODO this timeout is not to hit the rate limiter of OpenAI, remove it for production
                        if fixed_function_code is not None and fixed_function_code != "None" and fixed_function_code != "":
                            replace_function_in_c_file(file_path, item['function'], fixed_function_code, starting_line, ending_line)
                
                build_program(path, build_instr)
                is_crashing, report = run_program(path, run_instr, f"./{fuzzer_output_folder}/default/crashes/{new_file}")
                print(f"try #{it} - is_crashing: {is_crashing}")
                it += 1



            if it == 10 and is_crashing:
                with open(f"{logs_folder_name}/log.txt", 'a') as file:
                    file.write(f"Could not fix the program, moving on @ {time.ctime()}\n\n")

            elif it == 0:
                with open(f"{logs_folder_name}/log.txt", 'a') as file:
                    file.write(f"No fix needed, moving on @ {time.ctime()}\n\n")

            elif not is_crashing:
                with open(f"{logs_folder_name}/log.txt", 'a') as file:
                    file.write(f"fixed the issue in {it} try @ {time.ctime()}\n\n")
                print("successfully applied a fix\nStopping and restarting fuzzing")
                os.kill(fuzzer_pid, signal.SIGINT)
                print("    killed fuzzer")
                fuzzing_thread.join()
                print("stopped fuzzing thread & ", end='')
                stop_monitoring_event.set()
                monitoring_thread.join()
                print("stopped monitoring thread")
                inner_loop = False

    #|_|_| end of inner loop |_|_|#
    
#|_|_| end of outer loop |_|_|#
            

# --------------------------------------------------------- #