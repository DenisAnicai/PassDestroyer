import datetime
import subprocess
import sys
import time
import itertools
import string
import tqdm
import zipfile
import concurrent.futures
import multiprocessing
import threading
import argparse

def unzip_file(passwords):
    global archive_path
    global password_found
    global passwords_guessed
    global lock
    global initial_time
    global archive_path
    global correct_password

    z = zipfile.ZipFile(archive_path)

    if password_found.value:
        return

    passwords = [''.join(i).encode() for i in passwords]
    for i, password in enumerate(passwords):
        if password_found.value:
            return

        if i and i % 1000 == 0:
            with lock:
                passwords_guessed.value += 1000
        try:
            z.extractall(pwd=password)
            password_found.value = 1
            end_time = time.time()
            correct_password.value = password.decode()
            with open('logging.txt', 'a') as f:
                f.write(
                    f'Password found: {correct_password.decode()} in {end_time - initial_time:.2f} seconds with {passwords_guessed.value} passwords guessed / average speed: ({passwords_guessed.value / (end_time - initial_time):.2f} passwords per second)\n')
            return
        except:
            pass



def init_worker(shared_password_found, shared_passwords_guessed, shared_lock, shared_initial_time, shared_max_password_length, shared_archive_path, shared_correct_password):
    global password_found
    global passwords_guessed
    global lock
    global initial_time
    global max_password_length
    global archive_path
    global correct_password

    password_found = shared_password_found
    passwords_guessed = shared_passwords_guessed
    lock = shared_lock
    initial_time = shared_initial_time
    max_password_length = shared_max_password_length
    archive_path = shared_archive_path
    correct_password = shared_correct_password




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--number_of_processes', type=int, help='number of processes to use', default=16)
    # required arguments
    parser.add_argument('-l', '--max_password_length', type=int, help='max password length to guess', required=True)
    parser.add_argument('-p', '--archive_path', type=str, help='path to archive', required=True)
    args = parser.parse_args()

    number_of_processes = args.number_of_processes
    max_password_length = args.max_password_length
    archive_path = args.archive_path




    if number_of_processes < 1:
        print('Number of processes must be greater than 0')
        exit(1)

    if max_password_length < 1 or max_password_length > 10:
        print('Max password length must be greater than 0 and lower than 11')
        exit(1)

    try:
        z = zipfile.ZipFile(archive_path)
    except:
        print('Invalid archive path')
        exit(1)

    shared_password_found = multiprocessing.Value('i', 0)
    shared_passwords_guessed = multiprocessing.Value('i', 0)
    shared_lock = multiprocessing.Manager().Lock()
    shared_correct_password = multiprocessing.Manager().Value('s', '')

    initial_time = time.time()
    futures = set()
    with concurrent.futures.ProcessPoolExecutor(max_workers=number_of_processes, initializer=init_worker,
                                                initargs=(
            shared_password_found, shared_passwords_guessed, shared_lock, initial_time,
            max_password_length, archive_path, shared_correct_password)) as executor:

        threading.Thread(target=tqdm_thread_progress_bar).start()
        for password_length in range(1, 11):
            if shared_password_found.value == 1:
                break
            guesses = itertools.product(string.ascii_letters + string.digits, repeat=password_length)
            chunk_size = 100000
            # get chunks while there are still guesses left
            while True:
                if shared_password_found.value == 1:
                    break
                chunk = list(itertools.islice(guesses, chunk_size))
                if not chunk:
                    break

                futures.add(executor.submit(unzip_file, chunk))

                # while there are more than 100 tasks in the queue, wait
                while len(futures) > 100:
                    # if password was found, stop submitting tasks
                    if shared_password_found.value == 1:
                        break
                    futures = {f for f in futures if not f.done()}
                    time.sleep(0.1)

    end_time = time.time()
    # wait for all tasks to exit and for tqdm to finish
    while len(futures) > 0:
        futures = {f for f in futures if not f.done()}
        time.sleep(0.1)

    print(f'Password found: {shared_correct_password.value} in {end_time - initial_time:.2f} seconds with {shared_passwords_guessed.value} passwords guessed / average speed: ({shared_passwords_guessed.value / (end_time - initial_time):.2f} passwords per second)')
    exit(0)
