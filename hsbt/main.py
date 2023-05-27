import click

@click.command()
@click.option("--count", default=1, help="Number of greetings.")
@click.option("--name", prompt="Your name", help="The person to greet.")
def main(count, name):
    """Simple program that greets NAME for a total of COUNT times."""
    for _ in range(count):
        click.echo(f"Hello, {name}!")

def check_if_key_is_deployed():
    pass

def deploy_key():
    pass

def generate_key():
    pass

def mount_auto_fs():
    pass

def mount_fstab():
    pass

def ls_remote():
    pass

def download_remote():
    pass

def upload_remote():
    pass


if __name__ == '__main__':
    main()